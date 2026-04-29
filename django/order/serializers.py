from rest_framework import serializers
from django.utils import timezone
from .models import Order, OrderItem


# ─────────────────────────────────────────────
# 요청 Serializers
# ─────────────────────────────────────────────

class OrderItemStatusUpdateRequestSerializer(serializers.Serializer):
    """주문 아이템 상태 변경 요청"""
    order_item_id = serializers.IntegerField(
        error_messages={
            'required': 'order_item_id는 필수값입니다.',
            'invalid': 'order_item_id는 정수여야 합니다.',
        }
    )
    target_status = serializers.ChoiceField(
        choices=['COOKING', 'COOKED', 'SERVED', 'cooking', 'cooked', 'served'],
        error_messages={
            'required': 'target_status는 필수값입니다.',
            'invalid_choice': '유효하지 않은 상태값입니다: {value}',
        }
    )


class OrderItemCancelRequestSerializer(serializers.Serializer):
    """주문 아이템 취소 요청"""
    cancel_quantity = serializers.IntegerField(
        min_value=1,
        error_messages={
            'required': 'cancel_quantity는 필수값입니다.',
            'invalid': 'cancel_quantity는 정수여야 합니다.',
            'min_value': '취소 수량은 1 이상이어야 합니다.',
        }
    )


# ─────────────────────────────────────────────
# 응답 Serializers
# ─────────────────────────────────────────────

class OrderItemStatusUpdateResponseSerializer(serializers.Serializer):
    """주문 아이템 상태 변경 응답"""
    order_item_id = serializers.IntegerField()
    status = serializers.CharField()
    all_items_served = serializers.BooleanField()
    cooked_at = serializers.CharField(required=False, allow_null=True)
    served_at = serializers.CharField(required=False, allow_null=True)


class OrderItemCancelResponseSerializer(serializers.Serializer):
    """주문 아이템 취소 응답"""
    order_item_id = serializers.IntegerField()
    remaining_quantity = serializers.IntegerField()
    refund_amount = serializers.IntegerField()
    new_item_total_price = serializers.IntegerField()
    new_total_sales = serializers.IntegerField()


# ─────────────────────────────────────────────
# 주문 내역 (TableOrderHistory) Serializers
# ─────────────────────────────────────────────

class OrderHistoryItemSerializer(serializers.Serializer):
    """주문 내역 – 개별 아이템"""
    id = serializers.IntegerField()
    menu_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    image = serializers.CharField(allow_null=True)
    quantity = serializers.IntegerField()
    fixed_price = serializers.IntegerField()
    item_total_price = serializers.IntegerField()
    status = serializers.CharField()
    from_set = serializers.BooleanField()


class OrderHistoryOrderSerializer(serializers.Serializer):
    """주문 내역 – 주문 단위"""
    order_id = serializers.IntegerField()
    order_number = serializers.IntegerField()
    order_status = serializers.CharField()
    created_at = serializers.CharField()
    has_coupon = serializers.BooleanField()
    coupon_name = serializers.CharField(allow_null=True)
    table_coupon_id = serializers.IntegerField(allow_null=True)
    order_discount_price = serializers.IntegerField()
    order_fixed_price = serializers.IntegerField()
    order_items = OrderHistoryItemSerializer(many=True)


class TableOrderHistoryResponseSerializer(serializers.Serializer):
    """주문 내역 – 최종 응답 data (사용자용)"""
    table_usage_id = serializers.IntegerField()
    table_number = serializers.CharField()
    table_total_price = serializers.IntegerField()
    total_original_price = serializers.IntegerField()
    total_discount_price = serializers.IntegerField()
    order_list = OrderHistoryOrderSerializer(many=True)


class AdminTableOrderHistoryResponseSerializer(serializers.Serializer):
    """주문 내역 – 최종 응답 data (어드민용, 사용자용과 동일 구조)"""
    table_usage_id = serializers.IntegerField()
    table_number = serializers.CharField()
    table_total_price = serializers.IntegerField()
    total_original_price = serializers.IntegerField()
    total_discount_price = serializers.IntegerField()
    order_list = OrderHistoryOrderSerializer(many=True)