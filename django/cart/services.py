from datetime import timedelta
from django.db import transaction
from django.db.models import F, Sum, Case, When, IntegerField
from django.shortcuts import get_object_or_404
from django.utils import timezone

from table.models import *
from menu.models import *
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


@transaction.atomic
def add_to_cart(*, table_usage_id: int, type: str, menu_id: int | None, set_menu_id: int | None, quantity: int):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status == Cart.Status.PENDING:
        raise CartError("결제 진행 중에는 장바구니를 수정할 수 없습니다.", "CART_PENDING", status_code=409)
    if cart.status == Cart.Status.ORDERED:
        raise CartError("이미 주문된 장바구니입니다.", "CART_ORDERED", status_code=409)

    if quantity < 1:
        raise CartError("quantity는 1 이상이어야 합니다.", "VALIDATION_ERROR", status_code=400)

    if type == "menu":
        menu = get_object_or_404(Menu, id=menu_id)

        item = CartItem.objects.select_for_update().filter(cart=cart, menu=menu, setmenu__isnull=True).first()
        new_qty = quantity + (item.quantity if item else 0)

        _validate_menu_stock(menu, new_qty)

        unit_price = int(menu.price)
        if item:
            item.quantity = new_qty
            item.price_at_cart = unit_price
            item.save(update_fields=["quantity", "price_at_cart"])
        else:
            item = CartItem.objects.create(cart=cart, menu=menu, quantity=quantity, price_at_cart=unit_price)

    elif type == "setmenu":
        setmenu = get_object_or_404(SetMenu, id=set_menu_id)

        item = CartItem.objects.select_for_update().filter(cart=cart, setmenu=setmenu, menu__isnull=True).first()
        new_qty = quantity + (item.quantity if item else 0)

        _validate_setmenu_stock(setmenu, new_qty)

        unit_price = int(setmenu.price)
        if item:
            item.quantity = new_qty
            item.price_at_cart = unit_price
            item.save(update_fields=["quantity", "price_at_cart"])
        else:
            item = CartItem.objects.create(cart=cart, setmenu=setmenu, quantity=quantity, price_at_cart=unit_price)

    else:
        raise CartError("type은 menu 또는 setmenu 여야 합니다.", "VALIDATION_ERROR", status_code=400)

    recalc_cart_price(cart)
    return cart, item


@transaction.atomic
def update_item_quantity(*, table_usage_id: int, cart_item_id: int, quantity: int):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.ACTIVE:
        raise CartError("active 상태에서만 수정할 수 있습니다.", "CART_NOT_ACTIVE", status_code=409)

    item = CartItem.objects.select_for_update().get(id=cart_item_id, cart=cart)

    if quantity == 0:
        item.delete()
        recalc_cart_price(cart)
        return cart, None

    if item.menu_id:
        _validate_menu_stock(item.menu, quantity)
        item.price_at_cart = int(item.menu.price)
    else:
        _validate_setmenu_stock(item.setmenu, quantity)
        item.price_at_cart = int(item.setmenu.price)

    item.quantity = quantity
    item.save(update_fields=["quantity", "price_at_cart"])

    recalc_cart_price(cart)
    return cart, item


@transaction.atomic
def delete_item(*, table_usage_id: int, cart_item_id: int):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status != Cart.Status.ACTIVE:
        raise CartError("active 상태에서만 삭제할 수 있습니다.", "CART_NOT_ACTIVE", status_code=409)

    CartItem.objects.filter(id=cart_item_id, cart=cart).delete()
    recalc_cart_price(cart)
    return cart


@transaction.atomic
def enter_payment_info(*, table_usage_id: int):
    cart = get_or_create_cart_by_table_usage(table_usage_id)

    if cart.status == Cart.Status.PENDING:
        raise CartError("이미 결제 진행 중입니다.", "CART_PENDING", status_code=409)
    if cart.status != Cart.Status.ACTIVE:
        raise CartError("active 상태에서만 결제를 시작할 수 있습니다.", "CART_NOT_ACTIVE", status_code=409)

    recalc_cart_price(cart)

    for it in cart.items.select_related("menu", "setmenu"):
        if it.menu_id:
            _validate_menu_stock(it.menu, it.quantity)
        else:
            _validate_setmenu_stock(it.setmenu, it.quantity)

    cart.status = Cart.Status.PENDING
    cart.pending_expires_at = timezone.now() + timedelta(minutes=PENDING_TTL_MINUTES)
    cart.save(update_fields=["status", "pending_expires_at"])

    booth = cart.table_usage.table.booth
    amount = cart.cart_price

    payment = {
        "depositor": booth.depositor,
        "bank_name": booth.bank,
        "account": booth.account,
        "amount": amount,
    }
    return cart, payment