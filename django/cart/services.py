from datetime import timedelta
from django.db import transaction
from django.db.models import F, Sum, Case, When, IntegerField, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone

from booth.models import *
from table.models import *
from menu.models import *
from order.models import *
from .models import *

PENDING_TTL_MINUTES = 3

class CartError(Exception):
    def __init__(self, message, error_code="CART_ERROR", detail=None, available_stock=None, status_code=400):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.detail = detail or message
        self.available_stock = available_stock
        self.status_code = status_code


def _is_fee_booth(booth) -> bool:
    return booth.seat_type in [Booth.SEAT_TYPE.PP, Booth.SEAT_TYPE.PT]


def _can_add_fee_in_this_round(cart: Cart) -> bool:
    booth = cart.table_usage.table.booth

    if booth.seat_type == Booth.SEAT_TYPE.NO:
        return False
    if booth.seat_type == Booth.SEAT_TYPE.PP:
        return True
    if booth.seat_type == Booth.SEAT_TYPE.PT:
        return cart.round == 0
    return False


def _validate_fee_quantity_policy(*, booth: Booth, quantity: int):
    if booth.seat_type == Booth.SEAT_TYPE.NO:
        raise CartError(
            "이 부스는 자리비를 사용하지 않습니다.",
            "FEE_NOT_ENABLED",
            status_code=400,
        )

    if booth.seat_type == Booth.SEAT_TYPE.PT and quantity != 1:
        raise CartError(
            "테이블비는 1개만 담을 수 있습니다.",
            "INVALID_FEE_QUANTITY",
            status_code=400,
        )

    if booth.seat_type == Booth.SEAT_TYPE.PP and quantity < 1:
        raise CartError(
            "인당비 수량은 1 이상이어야 합니다.",
            "INVALID_FEE_QUANTITY",
            status_code=400,
        )



def _has_fee_item(cart: Cart) -> bool:
    return cart.items.filter(menu__category=Menu.Category.FEE).exists()


def _validate_required_fee_for_first_round(cart: Cart):
    booth = cart.table_usage.table.booth

    if cart.round != 0:
        return

    if not _is_fee_booth(booth):
        return

    if not _has_fee_item(cart):
        raise CartError(
            "첫 주문 시 자리비를 함께 담아야 합니다.",
            error_code="FEE_REQUIRED_FIRST_ORDER",
            detail="자리비 사용 부스는 첫 주문에 이용료(FEE) 메뉴가 반드시 포함되어야 합니다.",
            status_code=400,
        )


def _ensure_table_usage_alive(table_usage: TableUsage):
    if table_usage.ended_at is not None:
        raise CartError("이미 종료된 세션입니다.", "TABLE_USAGE_ENDED", status_code=410)


def _restore_if_pending_expired(cart: Cart) -> bool:
    if not cart.is_pending_expired():
        return False

    cart.status = Cart.Status.ACTIVE
    cart.pending_expires_at = None
    cart.save(update_fields=["status", "pending_expires_at"])
    return True


def _sync_item_prices_to_latest(cart: Cart) -> None:
    menu_price_subquery = Subquery(
        Menu.objects.filter(pk=OuterRef("menu_id")).values("price")[:1]
    )
    setmenu_price_subquery = Subquery(
        SetMenu.objects.filter(pk=OuterRef("setmenu_id")).values("price")[:1]
    )

    qs = CartItem.objects.filter(cart=cart)
    qs.update(
        price_at_cart=Case(
            When(menu__isnull=False, then=menu_price_subquery),
            When(setmenu__isnull=False, then=setmenu_price_subquery),
            default=F("price_at_cart"),
            output_field=IntegerField(),
        )
    )


def recalc_cart_price(cart: Cart) -> int:
    _sync_item_prices_to_latest(cart)
    total = cart.items.aggregate(s=Sum(F("quantity") * F("price_at_cart")))["s"] or 0
    cart.cart_price = int(total)
    cart.save(update_fields=["cart_price"])
    return cart.cart_price


def _validate_menu_stock(menu: Menu, want_qty: int):
    if menu.stock < want_qty:
        raise CartError(
            "재고가 부족합니다.",
            error_code="OUT_OF_STOCK",
            detail=f"{menu.name} 요청 수량 {want_qty}, 현재 재고 {menu.stock}",
            available_stock=menu.stock,
            status_code=400,
        )


def _build_required_menu_quantity_map(cart: Cart, *, override_item=None, override_quantity=None):
    """
    장바구니 전체 기준으로 각 단일 메뉴가 총 몇 개 필요한지 계산
    - 단품 메뉴 직접 담긴 수량
    - 세트메뉴 구성품 수량
    둘 다 합산
    """
    required = {}

    items = list(
        cart.items.select_related("menu", "setmenu").prefetch_related("setmenu__items__menu")
    )

    for item in items:
        qty = item.quantity

        if override_item is not None and item.id == override_item.id:
            qty = override_quantity

        if qty <= 0:
            continue

        if item.menu_id:
            # 자리비는 stock 대상으로 안 봄
            if item.menu.category != Menu.Category.FEE:
                required[item.menu_id] = required.get(item.menu_id, 0) + qty

        elif item.setmenu_id:
            for comp in item.setmenu.items.all():
                required[comp.menu_id] = required.get(comp.menu_id, 0) + (qty * comp.quantity)

    return required


def _validate_required_map(required_map: dict):
    if not required_map:
        return

    locked_menus = {
        m.id: m
        for m in Menu.objects.select_for_update().filter(id__in=required_map.keys())
    }

    for menu_id, want_qty in required_map.items():
        menu = locked_menus.get(menu_id)
        if menu is None:
            raise CartError(
                "존재하지 않는 메뉴가 포함되어 있습니다.",
                "MENU_NOT_FOUND",
                status_code=404,
            )
        _validate_menu_stock(menu, want_qty)


def _validate_cart_item_stock(cart: Cart, target_menu: Menu, new_direct_qty: int):
    existing_item = cart.items.filter(
        menu=target_menu,
        setmenu__isnull=True,
    ).first()

    if existing_item:
        required_map = _build_required_menu_quantity_map(
            cart,
            override_item=existing_item,
            override_quantity=new_direct_qty,
        )
    else:
        required_map = _build_required_menu_quantity_map(cart)
        if target_menu.category != Menu.Category.FEE:
            required_map[target_menu.id] = required_map.get(target_menu.id, 0) + new_direct_qty

    _validate_required_map(required_map)


def _validate_cart_setmenu_stock(cart: Cart, target_setmenu: SetMenu, new_set_qty: int):
    existing_item = cart.items.filter(
        setmenu=target_setmenu,
        menu__isnull=True,
    ).first()

    if existing_item:
        required_map = _build_required_menu_quantity_map(
            cart,
            override_item=existing_item,
            override_quantity=new_set_qty,
        )
    else:
        required_map = _build_required_menu_quantity_map(cart)
        comps = target_setmenu.items.select_related("menu").all()

        if not comps.exists():
            raise CartError(
                "세트 구성 정보가 없습니다.",
                "SETMENU_INVALID",
                status_code=400,
            )

        for comp in comps:
            required_map[comp.menu_id] = required_map.get(comp.menu_id, 0) + (new_set_qty * comp.quantity)

    _validate_required_map(required_map)
    
@transaction.atomic
def get_or_create_cart_by_table_usage(table_usage_id: int) -> Cart:
    table_usage = get_object_or_404(TableUsage, id=table_usage_id)
    _ensure_table_usage_alive(table_usage)

    cart, _ = Cart.objects.select_for_update().get_or_create(table_usage=table_usage)

    restored = _restore_if_pending_expired(cart)

    if restored:
        final_table_usage_id = cart.table_usage_id

        from .services_ws import broadcast_cart_event

        transaction.on_commit(
            lambda: broadcast_cart_event(
                table_usage_id=final_table_usage_id,
                event_type="CART_PENDING_EXPIRED",
                message="결제 대기 시간이 만료되어 장바구니가 다시 활성화되었습니다.",
            )
        )

    return cart

@transaction.atomic
def add_to_cart(*, table_usage_id: int, type: str, quantity: int, menu_id: int = None, set_menu_id: int = None):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.ACTIVE:
        raise CartError(
            "현재 장바구니는 수정할 수 없는 상태입니다.",
            "CART_NOT_ACTIVE",
            status_code=409,
        )

    booth = cart.table_usage.table.booth

    if type in ["menu", "fee"]:
        if not menu_id:
            raise CartError("menu_id가 필요합니다.", "INVALID_MENU_ID", status_code=400)

        menu = get_object_or_404(Menu.objects.select_for_update(), id=menu_id)

        if menu.booth_id != booth.pk:
            raise CartError(
                "현재 부스의 메뉴만 담을 수 있습니다.",
                "MENU_BOOTH_MISMATCH",
                status_code=400,
            )

        if type == "fee":
            if menu.category != Menu.Category.FEE:
                raise CartError(
                    "이용료 메뉴만 fee 타입으로 담을 수 있습니다.",
                    "INVALID_FEE_MENU",
                    status_code=400,
                )

            if not _can_add_fee_in_this_round(cart):
                raise CartError(
                    "자리비는 첫 주문에서만 담을 수 있습니다.",
                    "FEE_ONLY_FIRST_ROUND",
                    status_code=400,
                )

            item = CartItem.objects.select_for_update().filter(
                cart=cart,
                menu=menu,
                setmenu=None,
            ).first()

            new_qty = quantity if item is None else item.quantity + quantity
            _validate_fee_quantity_policy(booth=booth, quantity=new_qty)

            item, created = CartItem.objects.select_for_update().get_or_create(
                cart=cart,
                menu=menu,
                setmenu=None,
                defaults={
                    "quantity": quantity,
                    "price_at_cart": int(menu.price),
                },
            )

            if not created:
                item.quantity = new_qty
                item.price_at_cart = int(menu.price)
                item.save(update_fields=["quantity", "price_at_cart"])

        else:
            if menu.category == Menu.Category.FEE:
                raise CartError(
                    "이용료 메뉴는 fee 타입으로만 담을 수 있습니다.",
                    "INVALID_MENU_TYPE",
                    status_code=400,
                )

            item, created = CartItem.objects.select_for_update().get_or_create(
                cart=cart,
                menu=menu,
                setmenu=None,
                defaults={
                    "quantity": quantity,
                    "price_at_cart": int(menu.price),
                },
            )

            new_qty = quantity if created else item.quantity + quantity
            _validate_cart_item_stock(cart=cart, target_menu=menu, new_direct_qty=new_qty)

            if not created:
                item.quantity = new_qty
                item.price_at_cart = int(menu.price)
                item.save(update_fields=["quantity", "price_at_cart"])

    elif type == "setmenu":
        if not set_menu_id:
            raise CartError("set_menu_id가 필요합니다.", "INVALID_SETMENU_ID", status_code=400)

        setmenu = get_object_or_404(SetMenu.objects.select_for_update(), id=set_menu_id)

        if setmenu.booth_id != booth.pk:
            raise CartError(
                "현재 부스의 세트메뉴만 담을 수 있습니다.",
                "SETMENU_BOOTH_MISMATCH",
                status_code=400,
            )

        item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart,
            menu=None,
            setmenu=setmenu,
            defaults={
                "quantity": quantity,
                "price_at_cart": int(setmenu.price),
            },
        )

        new_qty = quantity if created else item.quantity + quantity
        _validate_cart_setmenu_stock(cart=cart, target_setmenu=setmenu, new_set_qty=new_qty)

        if not created:
            item.quantity = new_qty
            item.price_at_cart = int(setmenu.price)
            item.save(update_fields=["quantity", "price_at_cart"])

    else:
        raise CartError("type은 menu, fee 또는 setmenu여야 합니다.", "INVALID_TYPE", status_code=400)

    recalc_cart_price(cart)
    item.refresh_from_db()
    cart.refresh_from_db()

    return cart, item

@transaction.atomic
def update_item_quantity(*, table_usage_id: int, cart_item_id: int, quantity: int):
    cart = get_object_or_404(
        Cart.objects.select_for_update(),
        table_usage_id=table_usage_id,
    )

    if cart.status != Cart.Status.ACTIVE:
        raise CartError(
            "현재 장바구니는 수정할 수 없는 상태입니다.",
            "CART_NOT_ACTIVE",
            status_code=409,
        )

    item = get_object_or_404(
        CartItem.objects.select_for_update(),
        id=cart_item_id,
        cart=cart,
    )

    if quantity <= 0:
        item.delete()
        recalc_cart_price(cart)
        cart.refresh_from_db()
        return cart, None
    
    booth = cart.table_usage.table.booth

    if item.menu_id is not None:
        menu = get_object_or_404(
            Menu.objects.select_for_update(),
            id=item.menu_id,
        )

        if menu.category == Menu.Category.FEE:
            if not _can_add_fee_in_this_round(cart):
                raise CartError(
                    "자리비는 첫 주문에서만 수정할 수 있습니다.",
                    "FEE_ONLY_FIRST_ROUND",
                    status_code=400,
                )

            _validate_fee_quantity_policy(booth=booth, quantity=quantity)
            item.price_at_cart = int(menu.price)

        else:
            _validate_cart_item_stock(cart=cart, target_menu=menu, new_direct_qty=quantity)
            item.price_at_cart = int(menu.price)

    elif item.setmenu_id is not None:
        setmenu = get_object_or_404(
            SetMenu.objects.select_for_update(),
            id=item.setmenu_id,
        )

        _validate_cart_setmenu_stock(cart=cart, target_setmenu=setmenu, new_set_qty=quantity)
        item.price_at_cart = int(setmenu.price)

    else:
        raise CartError(
            "잘못된 장바구니 항목입니다.",
            "INVALID_CART_ITEM",
            status_code=400,
        )

    item.quantity = quantity
    item.save(update_fields=["quantity", "price_at_cart"])

    recalc_cart_price(cart)
    item.refresh_from_db()
    cart.refresh_from_db()

    return cart, item


@transaction.atomic
def delete_item(*, table_usage_id: int, cart_item_id: int):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.ACTIVE:
        raise CartError(
            "현재 장바구니는 수정할 수 없는 상태입니다.",
            "CART_NOT_ACTIVE",
            status_code=409,
        )

    item = get_object_or_404(
        CartItem.objects.select_for_update(),
        id=cart_item_id,
        cart=cart,
    )
    item.delete()

    recalc_cart_price(cart)
    cart.refresh_from_db()

    return cart

@transaction.atomic
def enter_payment_info(*, table_usage_id: int):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if not cart.items.exists():
        raise CartError(
            "장바구니가 비어 있습니다.",
            "EMPTY_CART",
            status_code=400,
        )

    if cart.status != Cart.Status.ACTIVE:
        raise CartError(
            "현재 결제를 진행할 수 없는 상태입니다.",
            "CART_NOT_ACTIVE",
            status_code=409,
        )

    _validate_required_fee_for_first_round(cart)

    subtotal = recalc_cart_price(cart)
    discount_total = 0
    total = subtotal - discount_total

    cart.status = Cart.Status.PENDING
    cart.pending_expires_at = timezone.now() + timedelta(minutes=PENDING_TTL_MINUTES)
    cart.save(update_fields=["status", "pending_expires_at"])

    booth = cart.table_usage.table.booth

    payment = {
        "depositor": booth.depositor,
        "bank_name": booth.bank,
        "account": booth.account,
        "amount": total,
    }

    return cart, payment

@transaction.atomic
def cancel_payment_and_restore_cart(*, table_usage_id: int) -> Cart:
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.PENDING:
        raise CartError(
            "현재 결제 취소가 가능한 상태가 아닙니다.",
            "CART_NOT_PENDING",
            status_code=409,
        )

    cart.status = Cart.Status.ACTIVE
    cart.pending_expires_at = None
    cart.save(update_fields=["status", "pending_expires_at"])

    final_table_usage_id = cart.table_usage_id

    from .services_ws import broadcast_cart_event

    transaction.on_commit(
        lambda: broadcast_cart_event(
            table_usage_id=final_table_usage_id,
            event_type="CART_PAYMENT_CANCELLED",
            message="결제가 취소되어 장바구니가 다시 활성화되었습니다.",
        )
    )

    return cart

def _calc_discount(subtotal: int, discount_type: str, discount_value) -> int:
    # 결제 확정 시점(Order 생성)에 '할인액/결제액'을 확정해야 해서 계산 필요
    if subtotal <= 0:
        return 0
    if discount_type == "RATE":
        # discount_value: Decimal(0.10) 같은 값
        amt = int(subtotal * float(discount_value))
        return max(0, min(subtotal, amt))
    # AMOUNT
    amt = int(discount_value)
    return max(0, min(subtotal, amt))


def _finalize_payment_core(cart: Cart):
    subtotal = recalc_cart_price(cart)

    cart_items = list(
        cart.items.select_related("menu", "setmenu").prefetch_related("setmenu__items__menu")
    )

    required_map = {}

    for it in cart_items:
        if it.menu_id:
            if it.menu.category != Menu.Category.FEE:
                required_map[it.menu_id] = required_map.get(it.menu_id, 0) + it.quantity
        else:
            comps = list(it.setmenu.items.all())
            if not comps:
                raise CartError("세트 구성 정보가 없습니다.", "SETMENU_INVALID", status_code=400)

            for comp in comps:
                required_map[comp.menu_id] = required_map.get(comp.menu_id, 0) + (it.quantity * comp.quantity)

    locked_menus = {
        m.id: m for m in Menu.objects.select_for_update().filter(id__in=required_map.keys())
    }

    setmenu_ids = [it.setmenu_id for it in cart_items if it.setmenu_id]
    set_components = {}

    if setmenu_ids:
        comps = (
            SetMenuItem.objects.select_related("menu")
            .select_for_update()
            .filter(set_menu_id__in=setmenu_ids)
        )
        for comp in comps:
            set_components.setdefault(comp.set_menu_id, []).append(comp)

        comp_menu_ids = list({comp.menu_id for comp in comps})
        extra_menus = Menu.objects.select_for_update().filter(id__in=comp_menu_ids)
        for m in extra_menus:
            locked_menus[m.id] = m

    for menu_id, want_qty in required_map.items():
        menu = locked_menus[menu_id]
        _validate_menu_stock(menu, want_qty)

    discount_total = 0
    applied_coupon = None

    try:
        from coupon.models import CartCouponApply

        applied = (
            CartCouponApply.objects.select_for_update()
            .filter(cart=cart, round=cart.round)
            .select_related("coupon_code", "coupon_code__coupon")
            .first()
        )
        if applied:
            applied_code = applied.coupon_code
            applied_coupon = applied_code.coupon

            if applied_code.used_at is not None:
                raise CartError(
                    "이미 사용된 쿠폰 코드입니다.",
                    "COUPON_CODE_USED",
                    status_code=409,
                )

            discount_total = _calc_discount(
                subtotal,
                applied_coupon.discount_type,
                applied_coupon.discount_value,
            )

            applied_code.used_at = timezone.now()
            applied_code.save(update_fields=["used_at"])
    except CartError:
        raise
    except Exception:
        pass

    order_price = subtotal - discount_total

    order = Order.objects.create(
        table_usage=cart.table_usage,
        cart=cart,
        order_price=order_price,
        original_price=subtotal,
        total_discount=discount_total,
        coupon_id=(applied_coupon.id if applied_coupon else None),
        order_status="PAID",
    )

    for it in cart_items:
        if it.menu_id:
            if it.menu.category == Menu.Category.FEE:
                menu = it.menu
            else:
                menu = locked_menus[it.menu_id]

            OrderItem.objects.create(
                order=order,
                menu=menu,
                setmenu=None,
                parent=None,
                quantity=it.quantity,
                fixed_price=int(it.price_at_cart),
                status="cooking",
            )

            if menu.category != Menu.Category.FEE:
                menu.stock = F("stock") - it.quantity
                menu.save(update_fields=["stock"])

        else:
            setmenu = it.setmenu
            parent_item = OrderItem.objects.create(
                order=order,
                menu=None,
                setmenu=setmenu,
                parent=None,
                quantity=it.quantity,
                fixed_price=int(it.price_at_cart),
                status="cooking",
            )

            comps = set_components.get(setmenu.id, [])
            if not comps:
                raise CartError("세트 구성 정보가 없습니다.", "SETMENU_INVALID", status_code=400)

            for comp in comps:
                child_menu = locked_menus[comp.menu_id]
                child_qty = it.quantity * comp.quantity

                OrderItem.objects.create(
                    order=order,
                    menu=child_menu,
                    setmenu=None,
                    parent=parent_item,
                    quantity=child_qty,
                    fixed_price=int(child_menu.price),
                    status="cooking",
                )

                child_menu.stock = F("stock") - child_qty
                child_menu.save(update_fields=["stock"])

    booth = cart.table_usage.table.booth
    Booth.objects.filter(pk=booth.pk).update(total_revenues=F("total_revenues") + order_price)

    return order

@transaction.atomic
def confirm_payment_and_mark_ordered(*, table_usage_id: int) -> Cart:
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.PENDING:
        raise CartError(
            "결제 진행 중인(PENDING) 상태에서만 확정할 수 있습니다.",
            "CART_NOT_PENDING",
            status_code=409,
        )

    _finalize_payment_core(cart)

    cart.status = Cart.Status.ORDERED
    cart.pending_expires_at = None
    cart.save(update_fields=["status", "pending_expires_at"])

    final_table_usage_id = cart.table_usage_id

    from .services_ws import broadcast_cart_event

    transaction.on_commit(
        lambda: broadcast_cart_event(
            table_usage_id=final_table_usage_id,
            event_type="CART_PAYMENT_CONFIRMED",
            message="결제가 확인되어 주문이 완료되었습니다.",
        )
    )

    return cart

@transaction.atomic
def reset_ordered_cart(*, table_usage_id: int) -> Cart:
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.ORDERED:
        raise CartError(
            "주문 완료(ORDERED) 상태에서만 장바구니를 초기화할 수 있습니다.",
            "CART_NOT_ORDERED",
            status_code=409,
        )

    cart.items.all().delete()

    cart.round += 1
    cart.status = Cart.Status.ACTIVE
    cart.pending_expires_at = None
    cart.save(update_fields=["round", "status", "pending_expires_at"])

    final_table_usage_id = cart.table_usage_id

    from .services_ws import broadcast_cart_event

    transaction.on_commit(
        lambda: broadcast_cart_event(
            table_usage_id=final_table_usage_id,
            event_type="CART_RESET",
            message="주문이 완료되어 장바구니가 초기화되었습니다.",
        )
    )

    return cart