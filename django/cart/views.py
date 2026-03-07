from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response

from table.models import TableUsage
from .models import *
from .serializers import *
from .services import *
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
        
        broadcast_cart_event(
            table_usage_id=table_usage_id,
            event_type="CART_ITEM_ADDED",
            message="장바구니에 메뉴가 추가되었습니다.",
        )

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
                    "item": {
                        "id": item.id,
                        "type": item.type,
                        "menu_id": item.menu_id,
                        "set_menu_id": item.setmenu_id,
                        "quantity": item.quantity,
                        "line_price": item.line_price,
                    },
                },
            },
            status=200,
        )


class CartDetailAPIView(APIView):
    """
    GET /api/v3/django/cart/detail/?table_usage_id=31
    """

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

        if cart.is_pending_expired():
            cart.status = Cart.Status.ACTIVE
            cart.pending_expires_at = None
            cart.save(update_fields=["status", "pending_expires_at"])

        recalc_cart_price(cart)

        items = []
        for it in cart.items.select_related("menu", "setmenu"):
            if it.menu_id:
                name = it.menu.name
                unit_price = int(it.menu.price)
                is_sold_out = it.menu.stock <= 0
            else:
                name = it.setmenu.name
                unit_price = int(it.setmenu.price)
                is_sold_out = False

            items.append(
                {
                    "id": it.id,
                    "type": it.type,
                    "menu_id": it.menu_id,
                    "set_menu_id": it.setmenu_id,
                    "name": name,
                    "unit_price": unit_price,
                    "quantity": it.quantity,
                    "line_price": it.line_price,
                    "is_sold_out": is_sold_out,
                }
            )

        coupon = {
            "applied": False,
            "coupon_id": None,
            "coupon_code": None,
            "discount_type": None,
            "discount_value": None,
            "discount_amount": None,
        }

        subtotal = cart.cart_price
        discount_total = 0
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
        
        broadcast_cart_event(
            table_usage_id=table_usage_id,
            event_type="CART_ITEM_UPDATED",
            message="장바구니 수량이 변경되었습니다.",
        )

        data = {"cart_price": cart.cart_price}
        if item:
            data["item"] = {"id": item.id, "quantity": item.quantity, "line_price": item.line_price}

        return Response({"message": "수량 변경 성공", "data": data}, status=200)


class CartDeleteItemAPIView(APIView):
    """
    DELETE /api/v3/django/cart/menu/delete/
    """

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
        
        broadcast_cart_event(
            table_usage_id=table_usage_id,
            event_type="CART_ITEM_DELETED",
            message="장바구니 항목이 삭제되었습니다.",
        )

        return Response({"message": "삭제 성공", "data": {"cart_price": cart.cart_price}}, status=200)


class CartPaymentInfoAPIView(APIView):
    """
    POST /api/v3/django/cart/payment-info/
    """

    def post(self, request):
        serializer = PaymentInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        table_usage_id = serializer.validated_data["table_usage_id"]

        try:
            cart, payment = enter_payment_info(table_usage_id=serializer.validated_data["table_usage_id"])
        except CartError as e:
            return error_response(e)
        
        broadcast_cart_event(
            table_usage_id=table_usage_id,
            event_type="CART_PAYMENT_PENDING",
            message="결제 확인 화면으로 이동했습니다.",
        )

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