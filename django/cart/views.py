from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction

from table.models import TableUsage
from coupon.models import CartCouponApply
from .models import *
from .serializers import *
from .services import (
    CartError,
    add_to_cart,
    get_or_create_cart_by_table_usage,
    recalc_cart_price,
    update_item_quantity,
    delete_item,
    enter_payment_info,
    cancel_payment_and_restore_cart,
    confirm_payment_and_mark_ordered,
    reset_ordered_cart,
    _is_fee_booth,
    _can_add_fee_in_this_round,
    build_cart_item_payload,
    _calc_discount,
)
from .services_ws import *


def error_response(e: CartError):
    return Response(
        {
            "message": e.message,
            "data": {
                "error_code": e.error_code,
                "detail": e.detail,
                "available_stock": e.available_stock,
            },
        },
        status=e.status_code,
    )


class CartAddAPIView(APIView):
    """
    POST /api/v3/django/cart/
    """
    authentication_classes = []

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        table_usage_id = serializer.validated_data["table_usage_id"]
        
        try:
            cart, item = add_to_cart(
                table_usage_id=serializer.validated_data["table_usage_id"],
                type=serializer.validated_data["type"],
                menu_id=serializer.validated_data.get("menu_id"),
                set_menu_id=serializer.validated_data.get("set_menu_id"),
                quantity=serializer.validated_data["quantity"],
            )
        except CartError as e:
            return error_response(e)
        
        transaction.on_commit(lambda: broadcast_cart_event(
            table_usage_id=table_usage_id,
            event_type="CART_ITEM_ADDED",
            message="장바구니에 메뉴가 추가되었습니다.",
        ))

        return Response(
            {
                "message": "장바구니 담기 성공",
                "data": {
                    "cart": {
                        "id": cart.id,
                        "table_usage_id": cart.table_usage_id,
                        "status": cart.status,
                        "cart_price": cart.cart_price,
                        "round": cart.round,
                    },
                    "item": build_cart_item_payload(item),
                },
            },
            status=200,
        )


class CartDetailAPIView(APIView):
    """
    GET /api/v3/django/cart/detail/?table_usage_id=31
    """
    authentication_classes = []

    def get(self, request):
        query_serializer = CartDetailQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        table_usage = get_object_or_404(TableUsage, id=query_serializer.validated_data["table_usage_id"])

        if table_usage.ended_at is not None:
            return Response(
                {
                    "message": "세션이 종료되었습니다.",
                    "data": {"error_code": "TABLE_USAGE_ENDED", "detail": "종료된 세션입니다."},
                },
                status=410,
            )

        cart = get_or_create_cart_by_table_usage(query_serializer.validated_data["table_usage_id"])

        recalc_cart_price(cart)

        items = []
        for it in cart.items.select_related("menu", "setmenu"):
            items.append(build_cart_item_payload(it))   # 여기 수정

        subtotal = cart.cart_price
        discount_total = 0
        coupon = {
            "applied": False,
            "coupon_id": None,
            "coupon_code": None,
            "discount_type": None,
            "discount_value": None,
            "discount_amount": 0,
        }

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

        total = subtotal - discount_total

        return Response(
            {
                "message": "장바구니 조회 성공",
                "data": {
                    "table_usage": {
                        "id": table_usage.id,
                        "table_id": table_usage.table_id,
                        "table_num": table_usage.table.table_num,
                        "booth_id": table_usage.table.booth_id,
                        "group_id": table_usage.table.group_id,
                        "started_at": table_usage.started_at,
                        "ended_at": table_usage.ended_at,
                    },
                    "cart": {
                        "id": cart.id,
                        "table_usage_id": cart.table_usage_id,
                        "status": cart.status,
                        "cart_price": cart.cart_price,
                        "pending_expires_at": cart.pending_expires_at,
                        "round": cart.round,
                        "created_at": cart.created_at,
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
                },
            },
            status=200,
        )


class CartUpdateQuantityAPIView(APIView):
    """
    PATCH /api/v3/django/cart/menu/
    """
    authentication_classes = []

    def patch(self, request):
        serializer = UpdateQuantitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        table_usage_id = serializer.validated_data["table_usage_id"]
        
        try:
            cart, item = update_item_quantity(
                table_usage_id=serializer.validated_data["table_usage_id"],
                cart_item_id=serializer.validated_data["cart_item_id"],
                quantity=serializer.validated_data["quantity"],
            )
        except CartError as e:
            return error_response(e)
        
        transaction.on_commit(lambda: broadcast_cart_event(
            table_usage_id=table_usage_id,
            event_type="CART_ITEM_UPDATED",
            message="장바구니 수량이 변경되었습니다.",
        ))

        data = {"cart_price": cart.cart_price}
        if item:
            data["item"] = build_cart_item_payload(item)
        return Response({"message": "수량 변경 성공", "data": data}, status=200)


class CartDeleteItemAPIView(APIView):
    """
    DELETE /api/v3/django/cart/menu/delete/
    """
    authentication_classes = []

    def delete(self, request):
        serializer = DeleteItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        table_usage_id = serializer.validated_data["table_usage_id"]
        
        try:
            cart = delete_item(
                table_usage_id=serializer.validated_data["table_usage_id"],
                cart_item_id=serializer.validated_data["cart_item_id"],
            )
        except CartError as e:
            return error_response(e)
        
        transaction.on_commit(lambda: broadcast_cart_event(
            table_usage_id=table_usage_id,
            event_type="CART_ITEM_DELETED",
            message="장바구니 항목이 삭제되었습니다.",
        ))

        return Response({"message": "삭제 성공", "data": {"cart_price": cart.cart_price}}, status=200)


class CartPaymentInfoAPIView(APIView):
    """
    POST /api/v3/django/cart/payment-info/
    """
    authentication_classes = []

    def post(self, request):
        serializer = PaymentInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        table_usage_id = serializer.validated_data["table_usage_id"]

        try:
            cart, payment = enter_payment_info(table_usage_id=serializer.validated_data["table_usage_id"])
        except CartError as e:
            return error_response(e)
        
        transaction.on_commit(lambda: broadcast_cart_event(
            table_usage_id=table_usage_id,
            event_type="CART_PAYMENT_PENDING",
            message="결제 확인 화면으로 이동했습니다.",
        ))

        return Response(
            {
                "message": "결제 확인 화면으로 이동합니다",
                "data": {
                    "cart": {
                        "id": cart.id,
                        "table_usage_id": cart.table_usage_id,
                        "status": cart.status,
                        "pending_expires_at": cart.pending_expires_at,
                        "round": cart.round,
                    },
                    "payment": payment,
                },
            },
            status=200,
        )
        
class CartPaymentCancelAPIView(APIView):
    """
    POST /api/v3/django/cart/payment-cancel/
    """
    authentication_classes = []

    def post(self, request):
        serializer = PaymentCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cart = cancel_payment_and_restore_cart(
                table_usage_id=serializer.validated_data["table_usage_id"]
            )
        except CartError as e:
            return error_response(e)

        return Response(
            {
                "message": "결제가 취소되어 장바구니가 다시 활성화되었습니다.",
                "data": {
                    "cart": {
                        "id": cart.id,
                        "table_usage_id": cart.table_usage_id,
                        "status": cart.status,
                        "pending_expires_at": cart.pending_expires_at,
                        "round": cart.round,
                    }
                },
            },
            status=200,
        )
        
class CartPaymentConfirmAPIView(APIView):
    """
    POST /api/v3/django/cart/payment-confirm/
    운영진이 결제 확인 슬라이드 완료 시 호출
    """
    authentication_classes = []

    def post(self, request):
        serializer = PaymentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cart = confirm_payment_and_mark_ordered(
                table_usage_id=serializer.validated_data["table_usage_id"]
            )
        except CartError as e:
            return error_response(e)

        return Response(
            {
                "message": "결제가 확인되어 주문이 완료되었습니다.",
                "data": {
                    "cart": {
                        "id": cart.id,
                        "table_usage_id": cart.table_usage_id,
                        "status": cart.status,
                        "pending_expires_at": cart.pending_expires_at,
                        "round": cart.round,
                    }
                },
            },
            status=200,
        )


class CartResetAPIView(APIView):
    """
    POST /api/v3/django/cart/reset/
    주문 완료 화면 처리 후 cart를 새 round로 초기화
    """
    authentication_classes = []

    def post(self, request):
        serializer = CartResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cart = reset_ordered_cart(
                table_usage_id=serializer.validated_data["table_usage_id"]
            )
        except CartError as e:
            return error_response(e)

        return Response(
            {
                "message": "장바구니가 초기화되었습니다.",
                "data": {
                    "cart": {
                        "id": cart.id,
                        "table_usage_id": cart.table_usage_id,
                        "status": cart.status,
                        "pending_expires_at": cart.pending_expires_at,
                        "round": cart.round,
                    }
                },
            },
            status=200,
        )