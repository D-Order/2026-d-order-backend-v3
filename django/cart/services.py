from datetime import timedelta
from django.db import transaction
from django.db.models import F, Sum, Case, When, IntegerField
from django.shortcuts import get_object_or_404
from django.utils import timezone

from booth.models import *
from table.models import *
from menu.models import *
from order.models import *
from .models import *

PENDING_TTL_MINUTES = 3

@transaction.atomic
def add_to_cart(*, table_usage_id: int, type: str, quantity: int, menu_id: int = None, set_menu_id: int = None):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.ACTIVE:
        raise CartError(
            "현재 장바구니는 수정할 수 없는 상태입니다.",
            "CART_NOT_ACTIVE",
            status_code=409,
        )

    if type == "menu":
        if not menu_id:
            raise CartError("menu_id가 필요합니다.", "INVALID_MENU_ID", status_code=400)

        menu = get_object_or_404(Menu.objects.select_for_update(), id=menu_id)
        _validate_menu_stock(menu, quantity)

        item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart,
            menu=menu,
            setmenu=None,
            defaults={
                "type": "menu",
                "quantity": quantity,
                "price_at_cart": menu.price,
            },
        )

        if not created:
            new_qty = item.quantity + quantity
            _validate_menu_stock(menu, new_qty)
            item.quantity = new_qty
            item.price_at_cart = menu.price
            item.save(update_fields=["quantity", "price_at_cart"])

    elif type == "setmenu":
        if not set_menu_id:
            raise CartError("set_menu_id가 필요합니다.", "INVALID_SETMENU_ID", status_code=400)

        setmenu = get_object_or_404(SetMenu, id=set_menu_id)
        _validate_setmenu_stock(setmenu, quantity)

        item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart,
            menu=None,
            setmenu=setmenu,
            defaults={
                "type": "setmenu",
                "quantity": quantity,
                "price_at_cart": setmenu.price,
            },
        )

        if not created:
            new_qty = item.quantity + quantity
            _validate_setmenu_stock(setmenu, new_qty)
            item.quantity = new_qty
            item.price_at_cart = setmenu.price
            item.save(update_fields=["quantity", "price_at_cart"])

    else:
        raise CartError("type은 menu 또는 setmenu여야 합니다.", "INVALID_TYPE", status_code=400)

    recalc_cart_price(cart)
    item.refresh_from_db()
    cart.refresh_from_db()

    return cart, item


@transaction.atomic
def update_item_quantity(*, table_usage_id: int, cart_item_id: int, quantity: int):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.ACTIVE:
        raise CartError(
            "현재 장바구니는 수정할 수 없는 상태입니다.",
            "CART_NOT_ACTIVE",
            status_code=409,
        )

    item = get_object_or_404(
        CartItem.objects.select_for_update().select_related("menu", "setmenu"),
        id=cart_item_id,
        cart=cart,
    )

    if quantity == 0:
        item.delete()
        recalc_cart_price(cart)
        cart.refresh_from_db()
        return cart, None

    if item.menu_id:
        menu = Menu.objects.select_for_update().get(id=item.menu_id)
        _validate_menu_stock(menu, quantity)
        item.price_at_cart = menu.price
    else:
        setmenu = SetMenu.objects.get(id=item.setmenu_id)
        _validate_setmenu_stock(setmenu, quantity)
        item.price_at_cart = setmenu.price

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

    subtotal = recalc_cart_price(cart)
    discount_total = 0
    total = subtotal - discount_total

    cart.status = Cart.Status.PENDING
    cart.pending_expires_at = timezone.now() + timedelta(minutes=PENDING_TTL_MINUTES)
    cart.save(update_fields=["status", "pending_expires_at"])

    payment = {
        "subtotal": subtotal,
        "discount_total": discount_total,
        "total": total,
        "expires_at": cart.pending_expires_at,
    }

    return cart, payment

class CartError(Exception):
    def __init__(self, message, error_code="CART_ERROR", detail=None, available_stock=None, status_code=400):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.detail = detail or message
        self.available_stock = available_stock
        self.status_code = status_code


def _ensure_table_usage_alive(table_usage: TableUsage):
    if table_usage.ended_at is not None:
        raise CartError("이미 종료된 세션입니다.", "TABLE_USAGE_ENDED", status_code=410)


def _restore_if_pending_expired(cart: Cart):
    if cart.is_pending_expired():
        cart.status = Cart.Status.ACTIVE
        cart.pending_expires_at = None
        cart.save(update_fields=["status", "pending_expires_at"])


def _sync_item_prices_to_latest(cart: Cart) -> None:
    qs = CartItem.objects.select_for_update().filter(cart=cart)
    qs.update(
        price_at_cart=Case(
            When(menu__isnull=False, then=F("menu__price")),
            When(setmenu__isnull=False, then=F("setmenu__price")),
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
            detail=f"요청 수량 {want_qty}, 현재 재고 {menu.stock}",
            available_stock=menu.stock,
            status_code=400,
        )


def _validate_setmenu_stock(setmenu: SetMenu, want_set_qty: int):
    comps = SetMenuItem.objects.filter(set_menu=setmenu).select_related("menu")
    if not comps.exists():
        raise CartError("세트 구성 정보가 없습니다.", "SETMENU_INVALID", status_code=400)

    for comp in comps:
        required = want_set_qty * comp.quantity
        if comp.menu.stock < required:
            raise CartError(
                "세트 구성품 재고가 부족합니다.",
                error_code="OUT_OF_STOCK",
                detail=f"{comp.menu.name} 필요수량 {required}, 현재재고 {comp.menu.stock}",
                available_stock=comp.menu.stock,
                status_code=400,
            )


@transaction.atomic
def get_or_create_cart_by_table_usage(table_usage_id: int) -> Cart:
    table_usage = get_object_or_404(TableUsage, id=table_usage_id)
    _ensure_table_usage_alive(table_usage)

    cart, _ = Cart.objects.select_for_update().get_or_create(table_usage=table_usage)
    _restore_if_pending_expired(cart)
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


@transaction.atomic
def finalize_payment_and_rotate_cart(*, table_usage_id: int) -> Cart:

    # 운영자 입금 확인(결제 확정) 시점에 호출되는 '최종 확정 처리' 훅
    # 여기서 주문 생성/재고 차감/매출 반영/쿠폰 used 처리까지 한 트랜잭션으로 묶음
    
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.PENDING:
        raise CartError(
            "결제 진행 중인(PENDING) 상태에서만 확정할 수 있습니다.",
            "CART_NOT_PENDING",
            status_code=409,
        )

    # 1) 최신 가격 동기화 + subtotal 확정
    subtotal = recalc_cart_price(cart)

    # 2) 재고 재검증 + (동시성) 관련 메뉴 row 잠금
    #    결제 확정 직전에 재고가 바뀌었을 수 있으니 마지막 가드 필요
    #    그리고 이후 stock 차감이 들어가므로 select_for_update로 잠그려고 함 !!!!!!!!!!
    cart_items = list(cart.items.select_related("menu", "setmenu"))

    # 단일 메뉴 잠금
    menu_ids = [it.menu_id for it in cart_items if it.menu_id]
    if menu_ids:
        locked_menus = {m.id: m for m in Menu.objects.select_for_update().filter(id__in=menu_ids)}
    else:
        locked_menus = {}

    # 세트 구성품 메뉴 잠금
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
        if comp_menu_ids:
            for m in Menu.objects.select_for_update().filter(id__in=comp_menu_ids):
                locked_menus[m.id] = m

    for it in cart_items:
        if it.menu_id:
            menu = locked_menus[it.menu_id]
            _validate_menu_stock(menu, it.quantity)
        else:
            comps = set_components.get(it.setmenu_id, [])
            if not comps:
                raise CartError("세트 구성 정보가 없습니다.", "SETMENU_INVALID", status_code=400)

            for comp in comps:
                menu = locked_menus[comp.menu_id]
                required = it.quantity * comp.quantity
                _validate_menu_stock(menu, required)

    # 3) 쿠폰(예약) 확인 + 결제액 확정 + used_at 최종 처리
    #    apply/cancel은 예약만. 확정(주문 생성) 시점에만 used_at을 찍어야 함.
    discount_total = 0
    applied_code = None
    applied_coupon = None

    try:
        from coupon.models import CartCouponApply  # 순환 import 최소화: 함수 내부 import
        applied = (
            CartCouponApply.objects.select_for_update()
            .filter(cart=cart, round=cart.round)
            .select_related("coupon_code", "coupon_code__coupon")
            .first()
        )
        if applied:
            applied_code = applied.coupon_code
            applied_coupon = applied_code.coupon

            # 이미 used면(다른 주문에서 확정된 코드) 충돌 처리
            if applied_code.used_at is not None:
                raise CartError(
                    "이미 사용된 쿠폰 코드입니다.",
                    "COUPON_CODE_USED",
                    status_code=409,
                )

            discount_total = _calc_discount(subtotal, applied_coupon.discount_type, applied_coupon.discount_value)

            # 결제 확정 시점에만 used_at 기록
            applied_code.used_at = timezone.now()
            applied_code.save(update_fields=["used_at"])
    except CartError:
        raise
    except Exception:
        pass

    order_price = subtotal - discount_total

    # 4) Order 생성 + OrderItem 생성
    order = Order.objects.create(
        table_usage=cart.table_usage,
        cart=cart,
        order_price=order_price,
        original_price=subtotal,
        total_discount=discount_total,
        coupon_id=(applied_coupon.id if applied_coupon else None),  # 모델 help_text는 "Spring 관리"지만 우선 로깅용으로라도 박아두는 게 유용
        order_status="PAID",
    )

    # OrderItem 생성 + 재고 차감까지 같이 처리
    for it in cart_items:
        if it.menu_id:
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

    # 5) Booth.total_revenues 반영
    booth = cart.table_usage.table.booth
    Booth.objects.filter(pk=booth.pk).update(total_revenues=F("total_revenues") + order_price)

    # 6) Cart 상태/라운드/아이템 정리 (재사용 정책)
    cart.status = Cart.Status.ORDERED
    cart.save(update_fields=["status"])

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