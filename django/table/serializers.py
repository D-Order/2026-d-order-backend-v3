from rest_framework import serializers
from .models import Table
from django.utils import timezone


class TableListSerializer(serializers.ModelSerializer):
    """테이블 리스트 조회 시 사용하는 시리얼라이저"""

    group = serializers.SerializerMethodField()
    accumulated_amount = serializers.SerializerMethodField()
    started_at = serializers.SerializerMethodField()
    order_list = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = [
            'table_num',
            'status',
            'group',
            'accumulated_amount',
            'started_at',
            'order_list'
        ]

    def _get_usage(self, obj):
        """context의 usage_map에서 꺼내거나 없으면 직접 조회 (fallback)"""
        usage_map = self.context.get('usage_map')
        if usage_map is not None:
            return usage_map.get(obj.pk)
        return obj.usages.filter(ended_at__isnull=True).first()

    def get_group(self, obj):
        if obj.group:
            return {'representative_table': obj.group.representative_table.table_num}
        return None

    def get_accumulated_amount(self, obj):
        usage = self._get_usage(obj)
        return usage.accumulated_amount if usage else None

    def get_started_at(self, obj):
        usage = self._get_usage(obj)
        if not usage or not usage.started_at:
            return None
        return timezone.localtime(usage.started_at).isoformat()

    def get_order_list(self, obj):
        from order.models import OrderItem
        usage = self._get_usage(obj)
        if not usage:
            return []
        items = (
            OrderItem.objects
            .filter(order__table_usage=usage, parent__isnull=True)
            .exclude(order__order_status='CANCELLED')
            .select_related('menu', 'setmenu')
            .order_by('-id')[:3]
        )
        return [
            {
                'name': item.setmenu.name if item.setmenu_id else (item.menu.name if item.menu else '알 수 없음'),
                'quantity': item.quantity,
                'created_at': timezone.localtime(item.created_at).isoformat()
            }
            for item in items
        ]
