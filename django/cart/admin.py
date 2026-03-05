from django.contrib import admin
from .models import *


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "table_usage", "status", "cart_price", "round", "pending_expires_at", "created_at")
    list_filter = ("status",)
    search_fields = ("table_usage__id",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "menu", "setmenu", "quantity", "price_at_cart", "created_at")
    search_fields = ("cart__id", "menu__name", "setmenu__name")