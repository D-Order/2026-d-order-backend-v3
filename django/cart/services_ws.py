import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from table.models import TableUsage
from cart.services import (
    get_or_create_cart_by_table_usage,
    recalc_cart_price,
    _calc_discount,
    _is_fee_booth,         
    _can_add_fee_in_this_round,
    build_cart_item_payload,
)

logger = logging.getLogger(__name__)


def build_cart_snapshot_data(table_usage_id: int):
    table_usage = TableUsage.objects.select_related("table", "table__booth").get(id=table_usage_id)
    cart = get_or_create_cart_by_table_usage(table_usage.id)
    recalc_cart_price(cart)

    items = []
    for it in cart.items.select_related("menu", "setmenu"):
        # 기존 직접 dict 만들던 부분 대신 공통 payload 사용
        items.append(build_cart_item_payload(it))

    subtotal = cart.cart_price

    coupon = {
        "applied": False,
        "coupon_id": None,
        "coupon_code": None,
        "discount_type": None,
        "discount_value": None,
        "discount_amount": 0,
    }
    discount_total = 0

    try:
        from coupon.models import CartCouponApply

        applied = (
            CartCouponApply.objects
            .filter(cart=cart, round=cart.round)
            .select_related("coupon_code", "coupon_code__coupon")
            .first()
        )

        if applied:
            cp = applied.coupon_code.coupon
            discount_total = _calc_discount(
                subtotal=subtotal,
                discount_type=cp.discount_type,
                discount_value=cp.discount_value,
            )

            coupon = {
                "applied": True,
                "coupon_id": cp.id,
                "coupon_code": applied.coupon_code.code,
                "discount_type": cp.discount_type,
                "discount_value": float(cp.discount_value),
                "discount_amount": discount_total,
            }

    except Exception as e:
        logger.warning(f"[Cart WS] coupon snapshot build failed: {e}")

    total = subtotal - discount_total

    return {
        "table_usage": {
            "id": table_usage.id,
            "table_id": table_usage.table_id,
            "table_num": table_usage.table.table_num,
            "booth_id": table_usage.table.booth_id,
            "group_id": table_usage.table.group_id,
            "started_at": table_usage.started_at.isoformat() if table_usage.started_at else None,
            "ended_at": table_usage.ended_at.isoformat() if table_usage.ended_at else None,
        },
        "cart": {
            "id": cart.id,
            "table_usage_id": cart.table_usage_id,
            "status": cart.status,
            "cart_price": cart.cart_price,
            "pending_expires_at": (
                cart.pending_expires_at.isoformat() if cart.pending_expires_at else None
            ),
            "round": cart.round,
            "created_at": cart.created_at.isoformat() if cart.created_at else None,
        },
        "fee_policy": {
            "seat_type": table_usage.table.booth.seat_type,
            "is_first_round": cart.round == 0,
            "has_fee_item": cart.items.filter(menu__category="FEE").exists(),
            "fee_required": _is_fee_booth(table_usage.table.booth) and cart.round == 0,
            "fee_addable": _can_add_fee_in_this_round(cart),
        },
        "items": items,
        "coupon": coupon,
        "summary": {
            "subtotal": subtotal,
            "discount_total": discount_total,
            "total": total,
        },
    }


def broadcast_cart_event(table_usage_id: int, event_type: str, message: str):
    channel_layer = get_channel_layer()
    group_name = f"table_usage_{table_usage_id}.cart"
    payload = build_cart_snapshot_data(table_usage_id)

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "cart_updated",
            "event_type": event_type,
            "message": message,
            "data": payload,
        },
    )