from django.contrib import admin
from .models import Order, OrderItem

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_table_id', 'get_table_num', 'order_price', 'order_status', 'created_at', 'updated_at')
    search_fields = ('id',)
    list_filter = ('order_status',)

    @admin.display(description='Table ID')
    def get_table_id(self, obj):
        return obj.table_usage.table_id if obj.table_usage else None

    @admin.display(description='테이블 번호')
    def get_table_num(self, obj):
        return obj.table_usage.table.table_num if obj.table_usage else None

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'get_table_num', 'menu', 'setmenu', 'parent', 'quantity', 'fixed_price', 'status', 'created_at')
    search_fields = ('id', 'order__id')
    list_filter = ('status',)

    @admin.display(description='테이블 번호')
    def get_table_num(self, obj):
        return obj.order.table_usage.table.table_num if obj.order and obj.order.table_usage else None
