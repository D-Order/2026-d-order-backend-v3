from django.test import TestCase
from order.models import Order, OrderItem
from menu.models import Menu, SetMenu, SetMenuItem
from table.models import Table, TableUsage, Booth
from cart.models import Cart


class MenuAggregationTest(TestCase):
    def test_setmenu_children_appear_in_aggregation(self):
        """세트메뉴 자식 아이템이 COOKING 상태일 때 메뉴 집계에 나타나는지 확인"""
        
        # Setup: 부스, 테이블, 주문
        booth = Booth.objects.create(booth_num=99, name='Test')
        table = Table.objects.create(table_num=99, booth=booth)
        table_usage = TableUsage.objects.create(table=table)
        cart = Cart.objects.create(table_usage=table_usage, status='ORDERED')
        order = Order.objects.create(
            table_usage=table_usage, order_price=0,
            order_status='PAID', cart=cart
        )
        
        # 메뉴 생성
        pizza = Menu.objects.create(
            name='Pizza', price=15000, category='FOOD', stock=100
        )
        cola = Menu.objects.create(
            name='Cola', price=3000, category='DRINK', stock=100
        )
        
        # 세트메뉴
        setmenu = SetMenu.objects.create(name='Pizza Set', price=18000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=pizza, quantity=1)
        SetMenuItem.objects.create(set_menu=setmenu, menu=cola, quantity=1)
        
        # 세트메뉴 부모 + 자식 OrderItem
        parent = OrderItem.objects.create(
            order=order, setmenu=setmenu, quantity=1,
            fixed_price=18000, status='COOKING'
        )
        pizza_item = OrderItem.objects.create(
            order=order, menu=pizza, parent=parent, quantity=1,
            fixed_price=0, status='COOKING'
        )
        cola_item = OrderItem.objects.create(
            order=order, menu=cola, parent=parent, quantity=1,
            fixed_price=0, status='COOKING'
        )
        
        # 메뉴 집계 쿼리
        qs = (
            OrderItem.objects
            .filter(
                order__order_status="PAID",
                order__table_usage__table__booth_id=booth.id,
                status__in=["COOKING"],
                menu__isnull=False,
            )
            .exclude(parent__isnull=True, setmenu__isnull=False)
            .exclude(menu__category="FEE")
            .select_related("menu")
        )
        
        # 검증
        aggregation = {}
        for item in qs:
            aggregation[item.menu.name] = aggregation.get(item.menu.name, 0) + item.quantity
        
        self.assertIn("Pizza", aggregation, "Pizza가 메뉴 집계에 나타나야 함")
        self.assertIn("Cola", aggregation, "Cola가 메뉴 집계에 나타나야 함")
        self.assertEqual(aggregation["Pizza"], 1)
        self.assertEqual(aggregation["Cola"], 1)
        
        print(f"✅ 메뉴 집계: {aggregation}")
