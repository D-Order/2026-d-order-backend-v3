from django.db import models
from django.utils import timezone
from booth.models import *
from table.models import *


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        RATE = "RATE", "퍼센트 할인"
        AMOUNT = "AMOUNT", "금액 할인"

    booth = models.ForeignKey(Booth, on_delete=models.CASCADE, related_name="coupons")
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=255, blank=True, null=True)

    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)

    quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.booth.name}] {self.name}"


class TableCoupon(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="table_coupons")
    table_usage = models.OneToOneField(
        TableUsage,
        on_delete=models.CASCADE,
        related_name="table_coupon"
    )
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TableUsage {self.table_usage_id} - Coupon {self.coupon_id}"
    
class CouponCode(models.Model):

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="codes")
    code = models.CharField(max_length=16, unique=True, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self):
        return self.code
