"""
table_usage_id=1 에 세트메뉴 주문 + 쿠폰 주문 추가
"""
import os, sys, django

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "../..")
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from table.models import Table, TableUsage
from menu.models import Menu, SetMenu, SetMenuItem
from cart.models import Cart, CartItem
from order.models import Order, OrderItem
from coupon.models import Coupon, TableCoupon
from booth.models import Booth

booth = Booth.objects.get(pk=1)
now = timezone.now()

# 기존 데이터 확인
tu = TableUsage.objects.get(pk=1)
print(f"TableUsage(1): table_id={tu.table_id}, table_num={tu.table.table_num}")

# 메뉴/세트메뉴/쿠폰 가져오기
menus = {m.name: m for m in Menu.objects.filter(booth=booth)}
setmenus = {sm.name: sm for sm in SetMenu.objects.filter(booth=booth)}
coupon = Coupon.objects.filter(booth=booth).first()

print(f"메뉴: {list(menus.keys())}")
print(f"세트메뉴: {list(setmenus.keys())}")
print(f"쿠폰: {coupon.name if coupon else 'None'}")

sm_a = setmenus["세트A"]  # 치킨+볶음밥 25000
sm_b = setmenus["세트B"]  # 치킨+콜라2 22000

# --- 주문 추가1: 세트A x1 (쿠폰 없음) ---
cart1, _ = Cart.objects.get_or_create(
    table_usage=tu,
    defaults={"status": "ordered", "cart_price": 0}
)
if cart1.status != "ordered":
    cart1.status = "ordered"
    cart1.save(update_fields=["status"])

order1 = Order.objects.create(
    table_usage=tu,
    cart=cart1,
    order_price=25000,
    original_price=25000,
    total_discount=0,
    coupon_id=None,
    order_status="PAID",
)
Order.objects.filter(pk=order1.pk).update(created_at=now - timedelta(minutes=30))

# 세트A 부모
parent_a = OrderItem.objects.create(
    order=order1, menu=None, setmenu=sm_a, parent=None,
    quantity=1, fixed_price=25000, status="COOKING",
)
# 세트A 자식들
for comp in SetMenuItem.objects.filter(set_menu=sm_a).select_related("menu"):
    OrderItem.objects.create(
        order=order1, menu=comp.menu, setmenu=None, parent=parent_a,
        quantity=comp.quantity, fixed_price=0, status="COOKING",
    )

print(f"✅ Order(id={order1.pk}) 세트A x1 = 25,000원")

# --- 주문 추가2: 콜라 x2 + 세트B x1, 쿠폰 사용 ---
order2 = Order.objects.create(
    table_usage=tu,
    cart=cart1,
    order_price=22000,  # 원가 28000 - 쿠폰 5000 = 23000... 아 계산
    original_price=28000,  # 콜라3000*2 + 세트B 22000 = 28000
    total_discount=5000,
    coupon_id=coupon.pk if coupon else None,
    order_status="PAID",
)
# order_price = 28000 - 5000 = 23000
Order.objects.filter(pk=order2.pk).update(created_at=now - timedelta(minutes=15))
order2.order_price = 23000
order2.save(update_fields=["order_price"])

# 콜라 x2
OrderItem.objects.create(
    order=order2, menu=menus["콜라"], setmenu=None, parent=None,
    quantity=2, fixed_price=3000, status="COOKING",
)

# 세트B 부모
parent_b = OrderItem.objects.create(
    order=order2, menu=None, setmenu=sm_b, parent=None,
    quantity=1, fixed_price=22000, status="COOKING",
)
# 세트B 자식들
for comp in SetMenuItem.objects.filter(set_menu=sm_b).select_related("menu"):
    OrderItem.objects.create(
        order=order2, menu=comp.menu, setmenu=None, parent=parent_b,
        quantity=comp.quantity, fixed_price=0, status="COOKING",
    )

# 쿠폰 사용 기록
if coupon:
    TableCoupon.objects.get_or_create(
        coupon=coupon,
        table_usage=tu,
        defaults={"used_at": now - timedelta(minutes=15)},
    )

print(f"✅ Order(id={order2.pk}) 콜라x2 + 세트B x1 + 쿠폰 = 원가28,000 - 할인5,000 = 23,000원")

# 누적금액 업데이트
tu.accumulated_amount = (tu.accumulated_amount or 0) + 25000 + 23000
tu.save(update_fields=["accumulated_amount"])

print()
print("=== table_usage_id=1 최종 상태 ===")
orders = Order.objects.filter(table_usage=tu).order_by("id")
for o in orders:
    coupon_str = " 🎟️쿠폰" if o.coupon_id else ""
    print(f"  Order(id={o.pk}) price={o.order_price:,} original={o.original_price} discount={o.total_discount}{coupon_str}")
    items = OrderItem.objects.filter(order=o).select_related("menu", "setmenu", "parent").order_by("id")
    for i in items:
        name = i.setmenu.name if i.setmenu_id else (i.menu.name if i.menu_id else "?")
        p = f" (child of {i.parent_id})" if i.parent_id else ""
        print(f"    Item(id={i.pk}) {name} qty={i.quantity} price={i.fixed_price:,} status={i.status}{p}")

tc = TableCoupon.objects.filter(table_usage=tu).first()
print(f"\nTableCoupon: {tc}")
print(f"누적금액: {tu.accumulated_amount:,}원")
print("\n🎉 완료!")
