from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
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
    """POST /api/v3/django/order/cancel/ - 운영자용 (인증 필요)"""
    permission_classes = [IsAuthenticated]

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
    authentication_classes = []
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

        response_data = OrderService.build_order_history_data(table_usage)
        response_serializer = TableOrderHistoryResponseSerializer(response_data)
        return Response({
            "message": "주문 내역 조회 완료",
            "data": response_serializer.data,
        }, status=status.HTTP_200_OK)
