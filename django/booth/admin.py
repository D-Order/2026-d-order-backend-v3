from django.contrib import admin
from django.utils.html import format_html
from .models import Booth


@admin.register(Booth)
class BoothAdmin(admin.ModelAdmin):
    list_display = (
        'pk',
        'name',
        'user',
        'seat_type',
        'table_max_cnt',
        'total_revenues_display',
        'location',
        'has_qr_image',
    )
    search_fields = ('user__username', 'name', 'account', 'depositor', 'location')
    list_filter = ('seat_type', 'bank')
    readonly_fields = ('qr_image_preview',)

    fieldsets = (
        ('기본 정보', {
            'fields': ('user', 'name', 'host_name', 'location', 'thumbnail_image'),
        }),
        ('테이블 설정', {
            'fields': ('table_max_cnt', 'table_limit_hours'),
        }),
        ('요금 설정', {
            'fields': ('seat_type', 'seat_fee_person', 'seat_fee_table'),
        }),
        ('은행 정보', {
            'fields': ('bank', 'account', 'depositor'),
        }),
        ('운영 정보', {
            'fields': ('operate_dates', 'total_revenues'),
        }),
        ('QR 코드', {
            'fields': ('qr_image', 'qr_image_preview'),
        }),
    )

    def total_revenues_display(self, obj):
        return f'{obj.total_revenues:,}원'
    total_revenues_display.short_description = '총 매출'
    total_revenues_display.admin_order_field = 'total_revenues'

    def has_qr_image(self, obj):
        return bool(obj.qr_image)
    has_qr_image.boolean = True
    has_qr_image.short_description = 'QR 생성됨'

    def qr_image_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" width="150" />', obj.qr_image.url)
        return '없음'
    qr_image_preview.short_description = 'QR 미리보기'
