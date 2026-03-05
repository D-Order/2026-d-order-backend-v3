"""테스트용 더미 주문 5개 생성 스크립트"""
import os, sys, django

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..")
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from table.models import TableUsage, Table
from menu.models import Menu, SetMenu
from cart.models import Cart
from order.models import Order, OrderItem
from booth.models import Booth

booth = Booth.objects.get(pk=1)

# ─── 더미 메뉴 생성 ───
menus_data = [
    ("오뎅탕", "MENU", 13500),
    ("쏘방관 치킨", "MENU", 18000),
    ("모둠전", "MENU", 15000),
    ("콜라", "DRINK", 3000),
    ("치킨", "MENU", 20000),
    ("볶음밥", "MENU", 10000),
    ("난장이가볶아올린작은밥밥", "MENU", 12000),
]
menus = {}
for name, cat, price in menus_data:
    m, _ = Menu.objects.get_or_create(
        booth=booth, name=name,
        defaults={"category": cat, "price": price, "stock": 100},
    )
    menus[name] = m
    print(f"Menu: {m.name} (id={m.pk})")

# 세트메뉴
sm, _ = SetMenu.objects.get_or_create(
    booth=booth, name="세트 A",
    defaults={"price": 25000},
)
print(f"SetMenu: {sm.name} (id={sm.pk})")

# ─── 주문 5개 생성 ───
now = timezone.now()

order_configs = [
    # (table_num, minutes_ago, items: [(menu_name, qty, status, is_set)])
    (1, 84, [
        ("오뎅탕", 10, "COOKING", False),
        ("쏘방관 치킨", 1, "COOKED", False),
        ("모둠전", 5, "SERVED", False),
    ]),
    (2, 71, [
        ("콜라", 10, "COOKING", True),
        ("치킨", 1, "COOKED", True),
        ("볶음밥", 5, "SERVED", True),
    ]),
    (3, 16, [
        ("난장이가볶아올린작은밥밥", 10, "COOKING", False),
        ("치킨", 1, "COOKED", False),
    ]),
    (4, 45, [
        ("오뎅탕", 3, "COOKING", False),
        ("콜라", 5, "COOKING", False),
    ]),
    (5, 5, [
        ("모둠전", 2, "COOKING", False),
        ("볶음밥", 3, "COOKING", False),
        ("치킨", 1, "COOKING", False),
    ]),
]

for table_num, mins_ago, items in order_configs:
    table = Table.objects.get(booth=booth, table_num=table_num)

    # TableUsage (없으면 생성)
    tu = TableUsage.objects.filter(table=table, ended_at__isnull=True).first()
    if not tu:
        tu = TableUsage.objects.create(
            table=table,
            started_at=now - timedelta(minutes=mins_ago + 10),
        )

    # Cart (없으면 생성, 있으면 ordered 로)
    try:
        cart = Cart.objects.get(table_usage=tu)
        if cart.status != "ordered":
            cart.status = "ordered"
            cart.save(update_fields=["status"])
    except Cart.DoesNotExist:
        cart = Cart(table_usage=tu, status="ordered", cart_price=0)
        cart.save()

    # Order
    total = sum(int(menus[n].price) * q for n, q, _, _ in items)
    order = Order.objects.create(
        table_usage=tu,
        cart=cart,
        order_price=total,
        original_price=total,
        total_discount=0,
        order_status="PAID",
    )
    # created_at 수동 설정 (auto_now_add 우회)
    Order.objects.filter(pk=order.pk).update(
        created_at=now - timedelta(minutes=mins_ago)
    )

    # OrderItem + 세트메뉴 자식 생성
    from menu.models import SetMenuItem
    for name, qty, status, is_set in items:
        menu = menus[name]
        parent_item = OrderItem.objects.create(
            order=order,
            menu=menu if not is_set else None,
            setmenu=sm if is_set else None,
            parent=None,
            quantity=qty,
            fixed_price=int(menu.price),
            status=status,
        )

        # 세트메뉴 → 구성품별 자식 OrderItem 생성
        if is_set:
            components = SetMenuItem.objects.filter(
                set_menu_id=sm.pk
            ).select_related("menu")
            for comp in components:
                OrderItem.objects.create(
                    order=order,
                    menu=comp.menu,
                    setmenu=None,
                    parent=parent_item,
                    quantity=qty * comp.quantity,
                    fixed_price=0,
                    status=status,
                )

    print(f"✅ Order(id={order.pk}) T{table_num} {mins_ago}분전 아이템{len(items)}개 total={total:,}")

print()
print(f"총 Order: {Order.objects.count()}")
print(f"총 OrderItem: {OrderItem.objects.count()}")
print("🎉 더미 데이터 생성 완료!")
