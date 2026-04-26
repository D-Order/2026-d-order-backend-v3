from django.contrib import admin
from .models import Coupon, CouponCode, TableCoupon, CartCouponApply


class CouponCodeInline(admin.TabularInline):
    model = CouponCode
    extra = 0
    readonly_fields = ('used_at', 'created_at')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('id', 'booth', 'name', 'discount_type', 'discount_value', 'quantity', 'created_at')
    list_filter = ('booth', 'discount_type')
    search_fields = ('name', 'booth__name')
    inlines = [CouponCodeInline]


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'coupon', 'code', 'used_at', 'created_at')
    list_filter = ('coupon__booth',)
    search_fields = ('code', 'coupon__name')
    readonly_fields = ('created_at',)


@admin.register(TableCoupon)
class TableCouponAdmin(admin.ModelAdmin):
    list_display = ('id', 'coupon', 'table_usage', 'used_at', 'created_at')
    list_filter = ('coupon__booth',)
    readonly_fields = ('created_at',)


@admin.register(CartCouponApply)
class CartCouponApplyAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'round', 'coupon_code', 'applied_at')
    readonly_fields = ('applied_at',)
