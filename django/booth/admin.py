from django.contrib import admin
from .models import Booth

# Register your models here.
@admin.register(Booth)
class BoothAdmin(admin.ModelAdmin):
    list_display = (
        "user",          
        "name",    
        "seat_type",    
        "seat_fee_person",
        "seat_fee_table",
        "bank",
        "account",
        "depositor",
        "has_qr_image",  # QR 생성 여부
    )
    search_fields = ("user__username", "name", "id", "account", "depositor")
    list_filter = ("seat_type", "bank")

    def booth_id(self, obj):
        return obj.id
    booth_id.short_description = "부스 ID"

    def booth_name(self, obj):
        return obj.name
    booth_name.short_description = "부스 이름"
    
    def has_qr_image(self, obj):
        return bool(obj.table_qr_image)
    has_qr_image.boolean = True
    has_qr_image.short_description = "QR 생성됨"