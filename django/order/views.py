from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.utils import timezone
from .services import OrderService
from .models import Order, OrderItem
from .serializers import (
    OrderItemStatusUpdateRequestSerializer,
    OrderItemStatusUpdateResponseSerializer,
    OrderItemCancelRequestSerializer,
    OrderItemCancelResponseSerializer,
    TableOrderHistoryResponseSerializer,
)
from table.models import Table, TableUsage


class OrderCancelAPIView(APIView):
    def post(self, request):
        event_data = request.data
        result = OrderService.handle_order_cancelled_event(event_data)
        if result == "success":
            return Response({"result": "success"}, status=status.HTTP_200_OK)
        elif result == "cart_not_found":
            return Response({"error": "cart_not_found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"result": result}, status=status.HTTP_400_BAD_REQUEST)


class OrderItemStatusUpdateAPIView(APIView):
    """주문 아이템 상태 변경 API (PATCH)"""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = OrderItemStatusUpdateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))[0]
            return Response(
                {"error": str(first_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order_item_id = serializer.validated_data["order_item_id"]
        target_status = serializer.validated_data["target_status"].upper()
        booth_id = request.user.booth.pk

        result = OrderService.update_order_item_status(
            order_item_id=order_item_id,
            target_status=target_status,
            booth_id=booth_id,
        )

        if "error" in result:
            error_status_map = {
                "invalid_status": status.HTTP_400_BAD_REQUEST,
                "not_found": status.HTTP_404_NOT_FOUND,
                "forbidden": status.HTTP_403_FORBIDDEN,
                "same_status": status.HTTP_400_BAD_REQUEST,
            }
            http_status = error_status_map.get(result["error"], status.HTTP_400_BAD_REQUEST)
            return Response(
                {"error": result["message"]},
                status=http_status,
            )

        response_serializer = OrderItemStatusUpdateResponseSerializer(result["data"])
        return Response(
            {"message": result["message"], "data": response_serializer.data},
            status=status.HTTP_200_OK,
        )


class OrderItemCancelAPIView(APIView):
    """개별 주문 아이템 취소 API (PATCH)"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, orderitem_id):
        serializer = OrderItemCancelRequestSerializer(data=request.data)
        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))[0]
            return Response(
                {"error": str(first_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cancel_quantity = serializer.validated_data["cancel_quantity"]
        booth_id = request.user.booth.pk

        result = OrderService.cancel_order_item(
            order_item_id=orderitem_id,
            cancel_quantity=cancel_quantity,
            booth_id=booth_id,
        )

        if "error" in result:
            error_status_map = {
                "not_found": status.HTTP_404_NOT_FOUND,
                "forbidden": status.HTTP_403_FORBIDDEN,
                "invalid_target": status.HTTP_400_BAD_REQUEST,
                "already_cancelled": status.HTTP_400_BAD_REQUEST,
                "invalid_quantity": status.HTTP_400_BAD_REQUEST,
                "exceed_quantity": status.HTTP_400_BAD_REQUEST,
            }
            http_status = error_status_map.get(result["error"], status.HTTP_400_BAD_REQUEST)
            return Response(
                {"error": result["message"]},
                status=http_status,
            )

        response_serializer = OrderItemCancelResponseSerializer(result["data"])
        return Response(
            {"message": result["message"], "data": response_serializer.data},
            status=status.HTTP_200_OK,
        )


class TableOrderHistoryAPIView(APIView):
    """
    GET /api/v3/django/order/table/{table_usage_id}/
    사용자가 현재 테이블 세션에서 주문한 모든 내역 조회 (인증 불필요)
    - 세트메뉴는 개별 구성품이 아닌 세트메뉴 단위로 표시
    - 주문별(order_list) 구조로 반환
    """
    permission_classes = [AllowAny]

    def get(self, request, table_usage_id):
        # ① 활성 테이블 세션 확인
        try:
            table_usage = (
                TableUsage.objects
                .select_related("table")
                .get(pk=table_usage_id)
            )
        except TableUsage.DoesNotExist:
            return Response(
                {"error": "테이블 세션을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if table_usage.ended_at is not None:
            return Response(
                {"error": "종료된 테이블 세션입니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        table = table_usage.table

        # ② 주문 조회 (CANCELLED 제외)
        orders = (
            Order.objects
            .filter(table_usage=table_usage)
            .exclude(order_status="CANCELLED")
            .order_by("created_at")
        )

        # ③ 쿠폰 정보 조회
        table_coupon = None
        coupon_name = None
        try:
            from coupon.models import TableCoupon
            tc = TableCoupon.objects.select_related("coupon").filter(
                table_usage=table_usage
            ).first()
            if tc:
                table_coupon = tc
                coupon_name = tc.coupon.name
        except Exception:
            pass

        # ④ 주문별 직렬화
        table_total_price = 0
        total_original_price = 0
        total_discount_price = 0
        order_list = []

        for order in orders:
            order_original = order.original_price or order.order_price
            order_discount = order.total_discount or 0
            order_fixed = order.order_price

            table_total_price += order_fixed
            total_original_price += order_original
            total_discount_price += order_discount

            has_coupon = order.coupon_id is not None

            # 부모 레벨 아이템만 (자식 제외) = 일반 메뉴 + 세트메뉴 부모
            parent_items = (
                OrderItem.objects
                .filter(order=order, parent__isnull=True)
                .select_related("menu", "setmenu")
                .order_by("id")
            )

            order_items = []
            for item in parent_items:
                if item.setmenu_id:
                    # 세트메뉴 (세트 단위로 표시)
                    name = item.setmenu.name
                    image = item.setmenu.image.url if item.setmenu.image else None
                    menu_id = item.setmenu_id
                    from_set = True
                else:
                    # 일반 메뉴
                    name = item.menu.name if item.menu else "알 수 없음"
                    image = item.menu.image.url if item.menu and item.menu.image else None
                    menu_id = item.menu_id
                    from_set = False

                order_items.append({
                    "id": item.pk,
                    "menu_id": menu_id,
                    "name": name,
                    "image": image,
                    "quantity": item.quantity,
                    "fixed_price": item.fixed_price,
                    "item_total_price": item.fixed_price * item.quantity,
                    "status": item.status,
                    "from_set": from_set,
                })

            order_list.append({
                "order_id": order.pk,
                "order_status": order.order_status,
                "created_at": timezone.localtime(order.created_at).isoformat(),
                "has_coupon": has_coupon,
                "coupon_name": coupon_name if has_coupon else None,
                "table_coupon_id": table_coupon.pk if (has_coupon and table_coupon) else None,
                "order_discount_price": order_discount,
                "order_fixed_price": order_fixed,
                "order_items": order_items,
            })

        response_data = {
            "table_usage_id": table_usage.pk,
            "table_number": str(table.table_num),
            "table_total_price": table_total_price,
            "total_original_price": total_original_price,
            "total_discount_price": total_discount_price,
            "order_list": order_list,
        }
        response_serializer = TableOrderHistoryResponseSerializer(response_data)
        return Response({
            "message": "주문 내역 조회 완료",
            "data": response_serializer.data,
        }, status=status.HTTP_200_OK)
