from rest_framework import serializers
from django.contrib.auth.models import User

from .models import Table

class TableListSerializer(serializers.ModelSerializer):
    """테이블 리스트 조회 시 사용하는 시리얼라이저"""

    group = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()
    recent_3_orders = serializers.SerializerMethodField()
    started_at = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = ['booth', 'table_num', 'status', 'group', 'total_revenue', 'recent_3_orders', 'started_at']
    
    def get_group(self, obj):
        """테이블 병합 그룹 정보 반환"""
        if obj.group:
            return {
                'representative_table': obj.group.representative_table.table_num
            }
        return None
    
    # TODO : 주문 내역 추가 (최근 3개)
    def get_recent_3_orders(self, obj):
        """테이블 최근 3개 주문 내역 반환"""
        return "notdevelpoed"
    
    #     recent_orders = obj.orders.order_by('-created_at')[:3]
    #     return OrderSerializer(recent_orders, many=True).data

    def get_total_revenue(self, obj):
        """테이블 총 수익 반환"""
        return "notdevelpoed"
    
    def get_started_at(self, obj):
        """테이블 사용 시작 시간 반환"""
        usage = obj.usages.filter(ended_at__isnull=True).first()
        if usage:
            return usage.started_at
        return None




class TableDetailSerializer(serializers.ModelSerializer):
    """테이블 상세 조회 시 사용하는 시리얼라이저"""
    
    orders = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = ['booth', 'table_num', 'status', 'group', 'orders']

    def get_orders(self, obj):
        """테이블 주문 내역 반환"""
        return "notdevelpoed"