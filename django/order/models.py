from django.db import models


class Order(models.Model):
    id = models.BigAutoField(primary_key=True)
    event_id = models.UUIDField(
        unique=True, null=True, blank=True,
        help_text='Redis 이벤트 UUID (멱등성 보장용)'
    )
    table_usage = models.ForeignKey(
        'table.TableUsage',
        on_delete=models.PROTECT,
        related_name='orders',
        help_text='이 주문이 속한 테이블 사용 기록'
    )
    cart = models.ForeignKey(
        'cart.Cart',
        on_delete=models.PROTECT,
        related_name='orders',
        null=True, blank=True,
        help_text='이 주문의 원본 장바구니'
    )
    order_price = models.IntegerField(help_text='실제 결제 금액 (할인 적용 후)')
    original_price = models.IntegerField(
        null=True, blank=True,
        help_text='할인 전 원가 총액'
    )
    total_discount = models.IntegerField(
        default=0,
        help_text='총 할인 금액'
    )
    coupon_id = models.IntegerField(
        null=True, blank=True,
        help_text='사용된 쿠폰 ID (Spring 쪽 관리)'
    )
    order_status = models.CharField(max_length=20)  # PAID, COMPLETED, CANCELLED
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "order"

    def __str__(self):
        return f"Order({self.pk}, table_usage={self.table_usage_id}, status={self.order_status})"


class OrderItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    menu = models.ForeignKey(
        'menu.Menu',
        on_delete=models.PROTECT,
        related_name='order_items',
        null=True,
        blank=True,
    )
    setmenu = models.ForeignKey(
        'menu.SetMenu',
        on_delete=models.PROTECT,
        related_name='order_items',
        null=True,
        blank=True,
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        null=True,
        blank=True,
        help_text='세트메뉴 구성품의 부모 OrderItem'
    )
    quantity = models.IntegerField()
    fixed_price = models.IntegerField()
    status = models.CharField(max_length=20)  # cooking, cooked, serving, served, cancelled
    created_at = models.DateTimeField(auto_now_add=True)
    cooked_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orderitem"

    def __str__(self):
        return f"OrderItem({self.pk}, order={self.order_id}, status={self.status})"
