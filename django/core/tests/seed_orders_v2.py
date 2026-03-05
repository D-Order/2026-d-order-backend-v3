"""
더미 주문 4개 생성 스크립트 (기존 데이터 삭제 후 재생성)
- 메뉴: 치킨(20000), 볶음밥(10000), 콜라(3000), 모둠전(15000)
- 세트A: 치킨1 + 볶음밥1 (25000)
- 세트B: 치킨1 + 콜라2 (22000)
- 주문1: T1 단일메뉴(치킨) x2
- 주문2: T2 단일메뉴(콜라) x1 + 세트A x1
- 주문3: T3 세트A x1 + 세트B x1, 쿠폰 사용
- 주문4: T4 단일메뉴(모둠전) x1, 쿠폰 사용
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

# ─── 기존 데이터 삭제 ───
print("🗑️  기존 데이터 삭제 중...")
OrderItem.objects.all().delete()
Order.objects.all().delete()
TableCoupon.objects.all().delete()
print(f"  삭제 완료")

# ─── 메뉴 생성 (4개) ───
menus_data = [
    ("치킨", "MENU", 20000),
    ("볶음밥", "MENU", 10000),
    ("콜라", "DRINK", 3000),
    ("모둠전", "MENU", 15000),
]
menus = {}
for name, cat, price in menus_data:
    m, _ = Menu.objects.get_or_create(
        booth=booth, name=name,
        defaults={"category": cat, "price": price, "stock": 100},
    )
    menus[name] = m
    print(f"  Menu: {m.name} (id={m.pk}, {price:,}원)")

# ─── 세트메뉴 생성 ───
# 세트A: 치킨1 + 볶음밥1 = 25000원
sm_a, _ = SetMenu.objects.get_or_create(
    booth=booth, name="세트A",
    defaults={"price": 25000},
)
# 기존 구성품 삭제 후 재생성
SetMenuItem.objects.filter(set_menu=sm_a).delete()
SetMenuItem.objects.create(set_menu=sm_a, menu=menus["치킨"], quantity=1)
SetMenuItem.objects.create(set_menu=sm_a, menu=menus["볶음밥"], quantity=1)
print(f"  SetMenu: {sm_a.name} (id={sm_a.pk}, 25,000원) = 치킨1 + 볶음밥1")

# 세트B: 치킨1 + 콜라2 = 22000원
sm_b, _ = SetMenu.objects.get_or_create(
    booth=booth, name="세트B",
    defaults={"price": 22000},
)
SetMenuItem.objects.filter(set_menu=sm_b).delete()
SetMenuItem.objects.create(set_menu=sm_b, menu=menus["치킨"], quantity=1)
SetMenuItem.objects.create(set_menu=sm_b, menu=menus["콜라"], quantity=2)
print(f"  SetMenu: {sm_b.name} (id={sm_b.pk}, 22,000원) = 치킨1 + 콜라2")

# ─── 쿠폰 생성 ───
coupon, _ = Coupon.objects.get_or_create(
    booth=booth, name="첫 주문 할인",
    defaults={
        "description": "첫 주문 시 5000원 할인",
        "discount_type": "AMOUNT",
        "discount_value": 5000,
        "quantity": 100,
    },
)
print(f"  Coupon: {coupon.name} (id={coupon.pk}, 5000원 할인)")

now = timezone.now()

# ─── 주문 생성 헬퍼 ───
def create_order(table_num, mins_ago, items_config, use_coupon=False):
    """
    items_config: list of (menu_name_or_None, setmenu_obj_or_None, qty, status)
    """
    table = Table.objects.get(booth=booth, table_num=table_num)
    
    tu = TableUsage.objects.filter(table=table, ended_at__isnull=True).first()
    if not tu:
        tu = TableUsage.objects.create(
            table=table,
            started_at=now - timedelta(minutes=mins_ago + 10),
        )
    
    # Cart
    try:
        cart = Cart.objects.get(table_usage=tu)
        if cart.status != "ordered":
            cart.status = "ordered"
            cart.save(update_fields=["status"])
    except Cart.DoesNotExist:
        cart = Cart(table_usage=tu, status="ordered", cart_price=0)
        cart.save()
    
    # 가격 계산
    total_original = 0
    for menu_name, setmenu, qty, status in items_config:
        if setmenu:
            total_original += setmenu.price * qty
        elif menu_name:
            total_original += menus[menu_name].price * qty
    
    discount = 0
    coupon_id_val = None
    if use_coupon:
        discount = 5000
        coupon_id_val = coupon.pk
    
    total_price = total_original - discount
    
    order = Order.objects.create(
        table_usage=tu,
        cart=cart,
        order_price=total_price,
        original_price=total_original,
        total_discount=discount,
        coupon_id=coupon_id_val,
        order_status="PAID",
    )
    Order.objects.filter(pk=order.pk).update(
        created_at=now - timedelta(minutes=mins_ago)
    )
    
    # TableUsage 누적 금액
    tu.accumulated_amount += total_price
    tu.save(update_fields=["accumulated_amount"])
    
    # OrderItem 생성 (세트메뉴면 자식도)
    for menu_name, setmenu, qty, status in items_config:
        if setmenu:
            parent_item = OrderItem.objects.create(
                order=order,
                menu=None,
                setmenu=setmenu,
                parent=None,
                quantity=qty,
                fixed_price=setmenu.price,
                status=status,
            )
            comps = SetMenuItem.objects.filter(set_menu=setmenu).select_related("menu")
            for comp in comps:
                OrderItem.objects.create(
                    order=order,
                    menu=comp.menu,
                    setmenu=None,
                    parent=parent_item,
                    quantity=qty * comp.quantity,
                    fixed_price=0,
                    status=status,
                )
        else:
            OrderItem.objects.create(
                order=order,
                menu=menus[menu_name],
                setmenu=None,
                parent=None,
                quantity=qty,
                fixed_price=menus[menu_name].price,
                status=status,
            )
    
    # 쿠폰 사용 시 TableCoupon 생성
    if use_coupon:
        TableCoupon.objects.get_or_create(
            coupon=coupon,
            table_usage=tu,
            defaults={"used_at": now - timedelta(minutes=mins_ago)},
        )
    
    item_count = OrderItem.objects.filter(order=order).count()
    coupon_str = " 🎟️쿠폰" if use_coupon else ""
    print(f"  ✅ Order(id={order.pk}) T{table_num} {mins_ago}분전 "
          f"원가={total_original:,} 할인={discount:,} 결제={total_price:,} "
          f"아이템={item_count}개{coupon_str}")
    return order

print()
print("📦 주문 생성 중...")

# 주문1: T1 치킨 x2 (단일메뉴)
# 원가: 20000 x 2 = 40,000
create_order(1, 60, [
    ("치킨", None, 2, "COOKING"),
])

# 주문2: T2 콜라 x1 + 세트A x1 (단일+세트)
# 원가: 3000 + 25000 = 28,000
create_order(2, 45, [
    ("콜라", None, 1, "COOKING"),
    (None, sm_a, 1, "COOKING"),
])

# 주문3: T3 세트A x1 + 세트B x1, 쿠폰
# 원가: 25000 + 22000 = 47,000 → 할인 5000 → 결제 42,000
create_order(3, 30, [
    (None, sm_a, 1, "COOKING"),
    (None, sm_b, 1, "COOKING"),
], use_coupon=True)

# 주문4: T4 모둠전 x1, 쿠폰
# 원가: 15000 → 할인 5000 → 결제 10,000
create_order(4, 15, [
    ("모둠전", None, 1, "COOKING"),
], use_coupon=True)

print()
print(f"총 Order: {Order.objects.count()}")
print(f"총 OrderItem: {OrderItem.objects.count()}")
print(f"총 TableCoupon: {TableCoupon.objects.count()}")

# 확인 출력
print("\n📋 전체 OrderItem 목록:")
items = OrderItem.objects.all().select_related(
    'order__table_usage__table', 'menu', 'setmenu', 'parent'
).order_by('order__id', 'id')
for i in items:
    t = i.order.table_usage.table.table_num
    name = (i.setmenu.name if i.setmenu_id 
            else (i.menu.name if i.menu_id else '?'))
    parent_str = f" (parent={i.parent_id})" if i.parent_id else ""
    print(f"  id={i.pk:3d}  T{t}  {name:10s} qty={i.quantity}  "
          f"price={i.fixed_price:>6,}  status={i.status}{parent_str}")

print("\n🎉 더미 데이터 생성 완료!")
