from django.contrib import admin
from .models import Table, TableGroup, TableUsage


class TableInline(admin.TabularInline):
    """TableGroup 상세 화면에서 소속 테이블 인라인 표시"""
    model = Table
    fields = ('table_num', 'status')
    extra = 0
    readonly_fields = ('table_num', 'status')
    can_delete = False
    show_change_link = True


class TableUsageInline(admin.TabularInline):
    """Table 상세 화면에서 사용 기록 인라인 표시"""
    model = TableUsage
    fields = ('started_at', 'ended_at', 'usage_minutes', 'accumulated_amount')
    extra = 0
    readonly_fields = ('started_at', 'ended_at', 'usage_minutes', 'accumulated_amount')
    can_delete = False
    ordering = ('-started_at',)


@admin.register(TableGroup)
class TableGroupAdmin(admin.ModelAdmin):
    list_display = ('pk', 'booth_name', 'representative_table_num', 'table_count', 'merged_at')
    list_filter = ('representative_table__booth__name',)
    search_fields = ('representative_table__booth__name',)
    readonly_fields = ('merged_at',)
    inlines = [TableInline]

    def booth_name(self, obj):
        if obj.representative_table:
            return obj.representative_table.booth.name
        return '-'
    booth_name.short_description = '부스'
    booth_name.admin_order_field = 'representative_table__booth__name'

    def representative_table_num(self, obj):
        if obj.representative_table:
            return obj.representative_table.table_num
        return '-'
    representative_table_num.short_description = '대표 테이블'
    representative_table_num.admin_order_field = 'representative_table__table_num'

    def table_count(self, obj):
        return obj.tables.count()
    table_count.short_description = '병합 테이블 수'


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('pk', 'booth', 'table_num', 'status', 'group')
    list_filter = ('status', 'booth__name')
    search_fields = ('booth__name', 'table_num')
    list_select_related = ('booth', 'group', 'group__representative_table')
    inlines = [TableUsageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('booth', 'group')


@admin.register(TableUsage)
class TableUsageAdmin(admin.ModelAdmin):
    list_display = (
        'pk',
        'booth_name',
        'table_num',
        'started_at',
        'ended_at',
        'usage_minutes',
        'accumulated_amount_display',
        'is_active',
    )
    list_filter = ('table__booth__name', 'table__status')
    search_fields = ('table__booth__name',)
    readonly_fields = ('started_at',)
    list_select_related = ('table', 'table__booth')
    date_hierarchy = 'started_at'

    def booth_name(self, obj):
        return obj.table.booth.name
    booth_name.short_description = '부스'
    booth_name.admin_order_field = 'table__booth__name'

    def table_num(self, obj):
        return obj.table.table_num
    table_num.short_description = '테이블 번호'
    table_num.admin_order_field = 'table__table_num'

    def accumulated_amount_display(self, obj):
        return f'{obj.accumulated_amount:,}원'
    accumulated_amount_display.short_description = '누적 금액'
    accumulated_amount_display.admin_order_field = 'accumulated_amount'

    def is_active(self, obj):
        return obj.ended_at is None
    is_active.boolean = True
    is_active.short_description = '사용중'
