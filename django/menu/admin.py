from django.contrib import admin
from .models import Menu, SetMenu, SetMenuItem


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ['id', 'booth', 'name', 'category', 'price', 'stock', 'is_soldout', 'created_at']
    list_filter = ['category', 'booth']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def is_soldout(self, obj):
        return obj.stock == 0
    is_soldout.boolean = True
    is_soldout.short_description = '품절'


class SetMenuItemInline(admin.TabularInline):
    """세트메뉴 구성 항목 인라인"""
    model = SetMenuItem
    extra = 1
    autocomplete_fields = ['menu']


@admin.register(SetMenu)
class SetMenuAdmin(admin.ModelAdmin):
    list_display = ['id', 'booth', 'name', 'category', 'price', 'item_count', 'created_at']
    list_filter = ['booth']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [SetMenuItemInline]
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = '구성 메뉴 수'


@admin.register(SetMenuItem)
class SetMenuItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'set_menu', 'menu', 'quantity']
    list_filter = ['set_menu']
    autocomplete_fields = ['set_menu', 'menu']
