"""쿠폰 더미 데이터 + 새 주문 테스트 스크립트"""
import os, sys, django

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from coupon.models import Coupon, TableCoupon
from order.models import Order
from booth.models import Booth
from django.utils import timezone

booth = Booth.objects.get(pk=1)

# 쿠폰 생성
coupon, _ = Coupon.objects.get_or_create(
    booth=booth, name="10% 할인 쿠폰",
    defaults={"description": "전 메뉴 10% 할인", "discount_type": "RATE", "discount_value": 10, "quantity": 100}
)
print(f"Coupon: {coupon.name} (id={coupon.pk})")

# Order 3개에 coupon_id 연결
orders = Order.objects.filter(order_status="PAID").order_by("created_at")[:3]
for o in orders:
    o.coupon_id = coupon.pk
    o.save(update_fields=["coupon_id"])
    tc, created = TableCoupon.objects.get_or_create(
        coupon=coupon,
        table_usage=o.table_usage,
        defaults={"used_at": timezone.now()}
    )
    tu = o.table_usage
    t = tu.table
    print(f"  Order(id={o.pk}) T{t.table_num} -> coupon_id={o.coupon_id}, TableCoupon created={created}")

print("Done!")
