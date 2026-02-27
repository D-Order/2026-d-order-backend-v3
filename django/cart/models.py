from django.db import models
from django.utils import timezone

from table.models import *
from menu.models import *


class Cart(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "active"
        PENDING = "pending_payment", "pending_payment"
        ORDERED = "ordered", "ordered"

    table_usage = models.OneToOneField(
        TableUsage,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    cart_price = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    pending_expires_at = models.DateTimeField(null=True, blank=True)
    round = models.IntegerField(default=0)

    def is_pending_expired(self) -> bool:
        return (
            self.status == self.Status.PENDING
            and self.pending_expires_at is not None
            and self.pending_expires_at < timezone.now()
        )

    def __str__(self):
        return f"Cart(table_usage={self.table_usage_id}, status={self.status})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, null=True, blank=True)
    setmenu = models.ForeignKey(SetMenu, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.IntegerField()
    price_at_cart = models.IntegerField()  # 담을 당시 단가
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def type(self) -> str:
        if self.menu_id:
            return "menu"
        if self.setmenu_id:
            return "setmenu"
        return "unknown"

    @property
    def line_price(self) -> int:
        return self.price_at_cart * self.quantity

    def __str__(self):
        return f"CartItem(cart={self.cart_id}, type={self.type}, qty={self.quantity})"