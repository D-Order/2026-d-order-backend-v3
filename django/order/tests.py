"""
order 앱 테스트

테스트 범위:
  - OrderService.update_order_item_status
  - OrderService.cancel_order_item
  - OrderService.create_order_from_event
  - OrderService.handle_serving_event
  - OrderService.handle_payment_rejected_event
  - REST API: OrderItemStatusUpdateAPIView (PATCH /status/)
  - REST API: OrderItemCancelAPIView (PATCH /<id>/cancel/)
  - REST API: TableOrderHistoryAPIView (GET /table/<id>/)
"""

import uuid
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from order.models import Order, OrderItem
from order.services import OrderService
from booth.models import Booth
from table.models import Table, TableUsage
from menu.models import Menu, SetMenu, SetMenuItem
from cart.models import Cart, CartItem

User = get_user_model()

CHANNEL_LAYERS_TEST = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}


# ─────────────────────────────────────────────
# 공통 Fixture Mixin
# ─────────────────────────────────────────────

class OrderTestMixin:
    """테스트용 데이터 세팅 믹스인"""

    def _create_booth_and_table(self, username="testuser"):
        user = User.objects.create_user(username=username, password="pass1234")
        booth = Booth.objects.create(
            user=user,
            name="테스트부스",
            account="123-456",
            depositor="홍길동",
            bank="테스트은행",
            table_max_cnt=10,
            table_limit_hours=2,
        )
        table = Table.objects.create(booth=booth, table_num=1)
        table_usage = TableUsage.objects.create(
            table=table, started_at=timezone.now()
        )
        return user, booth, table, table_usage

    def _create_menu(self, booth, name="떡볶이", price=5000, stock=100):
        return Menu.objects.create(
            booth=booth, name=name, price=price, stock=stock
        )

    def _create_set_menu(self, booth, name="세트A", price=12000, menus=None):
        """세트메뉴 + SetMenuItem 구성품 생성

        menus: [(Menu, quantity), ...]
        """
        setmenu = SetMenu.objects.create(booth=booth, name=name, price=price)
        if menus:
            for menu, qty in menus:
                SetMenuItem.objects.create(set_menu=setmenu, menu=menu, quantity=qty)
        return setmenu

    def _create_order_with_items(self, table_usage, items_data, order_price=None):
        """Order + OrderItem 생성

        items_data: [
            {"menu": Menu|None, "setmenu": SetMenu|None, "quantity": int,
             "fixed_price": int, "status": str, "parent": OrderItem|None},
        ]
        """
        total = order_price or sum(
            d["fixed_price"] * d["quantity"]
            for d in items_data if d.get("parent") is None
        )
        order = Order.objects.create(
            table_usage=table_usage,
            order_price=total,
            original_price=total,
            order_status="PAID",
        )
        created_items = []
        for d in items_data:
            item = OrderItem.objects.create(
                order=order,
                menu=d.get("menu"),
                setmenu=d.get("setmenu"),
                parent=d.get("parent"),
                quantity=d["quantity"],
                fixed_price=d["fixed_price"],
                status=d.get("status", "COOKING"),
            )
            created_items.append(item)
        return order, created_items


# ═════════════════════════════════════════════
# OrderService.update_order_item_status 테스트
# ═════════════════════════════════════════════

@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class UpdateOrderItemStatusTest(TransactionTestCase, OrderTestMixin):

    def setUp(self):
        self.user, self.booth, self.table, self.table_usage = (
            self._create_booth_and_table()
        )
        self.menu = self._create_menu(self.booth)
        self.booth_id = self.booth.pk

    # ── 정상 케이스 ──

    @patch("core.redis_client.publish")
    def test_cooking_to_cooked(self, mock_publish):
        """COOKING → COOKED 상태 변경 + Redis 발행"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 2, "fixed_price": 5000}],
        )

        result = OrderService.update_order_item_status(
            item.pk, "COOKED", self.booth_id
        )

        assert result["success"] is True
        assert result["data"]["status"] == "COOKED"
        assert result["data"]["cooked_at"] is not None

        item.refresh_from_db()
        assert item.status == "COOKED"
        assert item.cooked_at is not None

        # Redis publish (cooked 채널) 호출 확인
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert "cooked" in call_args[0][0]

    def test_cooked_to_served(self):
        """COOKED → SERVED 상태 변경"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000, "status": "COOKED"}],
        )

        result = OrderService.update_order_item_status(
            item.pk, "SERVED", self.booth_id
        )

        assert result["success"] is True
        assert result["data"]["status"] == "SERVED"
        assert result["data"]["served_at"] is not None

        item.refresh_from_db()
        assert item.status == "SERVED"
        assert item.served_at is not None

    def test_all_served_completes_order(self):
        """모든 아이템 SERVED 시 Order → COMPLETED"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000, "status": "COOKED"}],
        )

        result = OrderService.update_order_item_status(
            item.pk, "SERVED", self.booth_id
        )

        assert result["data"]["all_items_served"] is True

        order.refresh_from_db()
        assert order.order_status == "COMPLETED"

    def test_partial_served_does_not_complete(self):
        """일부만 SERVED면 COMPLETED 안 됨"""
        order, [item1, item2] = self._create_order_with_items(
            self.table_usage,
            [
                {"menu": self.menu, "quantity": 1, "fixed_price": 5000, "status": "COOKED"},
                {"menu": self.menu, "quantity": 1, "fixed_price": 3000, "status": "COOKING"},
            ],
        )

        result = OrderService.update_order_item_status(
            item1.pk, "SERVED", self.booth_id
        )

        assert result["data"]["all_items_served"] is False

        order.refresh_from_db()
        assert order.order_status == "PAID"

    # ── 에러 케이스 ──

    def test_invalid_status(self):
        """유효하지 않은 상태값"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000}],
        )

        result = OrderService.update_order_item_status(
            item.pk, "INVALID", self.booth_id
        )

        assert result["error"] == "invalid_status"

    def test_not_found(self):
        """존재하지 않는 아이템 ID"""
        result = OrderService.update_order_item_status(
            99999, "COOKED", self.booth_id
        )

        assert result["error"] == "not_found"

    def test_same_status(self):
        """이미 같은 상태"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000, "status": "COOKED"}],
        )

        result = OrderService.update_order_item_status(
            item.pk, "COOKED", self.booth_id
        )

        assert result["error"] == "same_status"

    def test_wrong_booth_forbidden(self):
        """다른 부스의 주문 변경 시도"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000}],
        )

        result = OrderService.update_order_item_status(
            item.pk, "COOKED", booth_id=9999
        )

        assert result["error"] == "forbidden"

    def test_setmenu_parent_blocked(self):
        """세트메뉴 부모 아이템 직접 상태 변경 불가"""
        setmenu = self._create_set_menu(self.booth)
        order, [parent, child] = self._create_order_with_items(
            self.table_usage,
            [
                {"setmenu": setmenu, "quantity": 1, "fixed_price": 12000},
                {"menu": self.menu, "quantity": 1, "fixed_price": 0, "parent": None},
            ],
        )
        # parent에 setmenu가 있고 parent_id가 None인 경우
        child.parent = parent
        child.save()

        result = OrderService.update_order_item_status(
            parent.pk, "COOKED", self.booth_id
        )

        assert result["error"] == "invalid_target"


# ═════════════════════════════════════════════
# OrderService.cancel_order_item 테스트
# ═════════════════════════════════════════════

@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class CancelOrderItemTest(TransactionTestCase, OrderTestMixin):

    def setUp(self):
        self.user, self.booth, self.table, self.table_usage = (
            self._create_booth_and_table()
        )
        self.menu = self._create_menu(self.booth, stock=100)
        self.booth_id = self.booth.pk

    @patch("core.redis_client.publish")
    def test_full_cancel(self, mock_publish):
        """전체 수량 취소 → CANCELLED + 재고 복구"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 3, "fixed_price": 5000}],
        )
        self.table_usage.accumulated_amount = 15000
        self.table_usage.save()

        result = OrderService.cancel_order_item(item.pk, 3, self.booth_id)

        assert result["success"] is True
        assert result["data"]["remaining_quantity"] == 0
        assert result["data"]["refund_amount"] == 15000

        item.refresh_from_db()
        assert item.status == "CANCELLED"
        assert item.quantity == 0

        # 재고 복구 확인
        self.menu.refresh_from_db()
        assert self.menu.stock == 103  # 100 + 3

        # TableUsage 차감 확인
        self.table_usage.refresh_from_db()
        assert self.table_usage.accumulated_amount == 0

    @patch("core.redis_client.publish")
    def test_partial_cancel(self, mock_publish):
        """부분 수량 취소"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 5, "fixed_price": 3000}],
        )
        self.table_usage.accumulated_amount = 15000
        self.table_usage.save()

        result = OrderService.cancel_order_item(item.pk, 2, self.booth_id)

        assert result["success"] is True
        assert result["data"]["remaining_quantity"] == 3
        assert result["data"]["refund_amount"] == 6000

        item.refresh_from_db()
        assert item.status == "COOKING"  # 수량 남아있으므로 상태 유지
        assert item.quantity == 3

    @patch("core.redis_client.publish")
    def test_all_items_cancelled_marks_order(self, mock_publish):
        """모든 아이템 취소 → Order.order_status = CANCELLED"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000}],
        )
        self.table_usage.accumulated_amount = 5000
        self.table_usage.save()

        OrderService.cancel_order_item(item.pk, 1, self.booth_id)

        order.refresh_from_db()
        assert order.order_status == "CANCELLED"

    @patch("core.redis_client.publish")
    def test_setmenu_cancel_cascades_to_children(self, mock_publish):
        """세트메뉴 취소 → 자식 아이템 + 구성품 재고 복구"""
        menu1 = self._create_menu(self.booth, name="버거", stock=50)
        menu2 = self._create_menu(self.booth, name="콜라", stock=50)
        setmenu = self._create_set_menu(
            self.booth, menus=[(menu1, 1), (menu2, 1)]
        )

        order = Order.objects.create(
            table_usage=self.table_usage,
            order_price=12000,
            original_price=12000,
            order_status="PAID",
        )
        parent = OrderItem.objects.create(
            order=order, setmenu=setmenu, quantity=2,
            fixed_price=6000, status="COOKING",
        )
        child1 = OrderItem.objects.create(
            order=order, menu=menu1, parent=parent,
            quantity=2, fixed_price=0, status="COOKING",
        )
        child2 = OrderItem.objects.create(
            order=order, menu=menu2, parent=parent,
            quantity=2, fixed_price=0, status="COOKING",
        )

        self.table_usage.accumulated_amount = 12000
        self.table_usage.save()

        result = OrderService.cancel_order_item(parent.pk, 1, self.booth_id)

        assert result["success"] is True
        assert result["data"]["remaining_quantity"] == 1

        parent.refresh_from_db()
        assert parent.quantity == 1

        child1.refresh_from_db()
        assert child1.quantity == 1

        menu1.refresh_from_db()
        assert menu1.stock == 51  # 50 + 1

        menu2.refresh_from_db()
        assert menu2.stock == 51

    # ── 에러 케이스 ──

    def test_child_item_cancel_blocked(self):
        """세트메뉴 자식 직접 취소 불가"""
        setmenu = self._create_set_menu(self.booth)
        order = Order.objects.create(
            table_usage=self.table_usage,
            order_price=12000, original_price=12000, order_status="PAID",
        )
        parent = OrderItem.objects.create(
            order=order, setmenu=setmenu, quantity=1,
            fixed_price=12000, status="COOKING",
        )
        child = OrderItem.objects.create(
            order=order, menu=self.menu, parent=parent,
            quantity=1, fixed_price=0, status="COOKING",
        )

        result = OrderService.cancel_order_item(child.pk, 1, self.booth_id)

        assert result["error"] == "invalid_target"

    def test_already_cancelled(self):
        """이미 취소된 아이템"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 0, "fixed_price": 5000, "status": "CANCELLED"}],
        )

        result = OrderService.cancel_order_item(item.pk, 1, self.booth_id)

        assert result["error"] == "already_cancelled"

    def test_exceed_quantity(self):
        """취소 수량 초과"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 2, "fixed_price": 5000}],
        )

        result = OrderService.cancel_order_item(item.pk, 5, self.booth_id)

        assert result["error"] == "exceed_quantity"

    def test_cancel_not_found(self):
        result = OrderService.cancel_order_item(99999, 1, self.booth_id)
        assert result["error"] == "not_found"

    def test_cancel_wrong_booth(self):
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000}],
        )

        result = OrderService.cancel_order_item(item.pk, 1, booth_id=9999)

        assert result["error"] == "forbidden"

    @patch("core.redis_client.publish")
    def test_order_price_decreases(self, mock_publish):
        """취소 시 Order.order_price 차감"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 4, "fixed_price": 3000}],
        )
        self.table_usage.accumulated_amount = 12000
        self.table_usage.save()

        OrderService.cancel_order_item(item.pk, 2, self.booth_id)

        order.refresh_from_db()
        assert order.order_price == 6000  # 12000 - 6000


# ═════════════════════════════════════════════
# OrderService.create_order_from_event 테스트
# ═════════════════════════════════════════════

@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class CreateOrderFromEventTest(TransactionTestCase, OrderTestMixin):

    def setUp(self):
        self.user, self.booth, self.table, self.table_usage = (
            self._create_booth_and_table()
        )
        self.menu = self._create_menu(self.booth, stock=50)
        self.booth_id = self.booth.pk

    def _make_cart(self, items_data=None):
        """Cart + CartItem 생성

        items_data: [{"menu": Menu, "quantity": int, "price": int}, ...]
        """
        cart = Cart.objects.create(
            table_usage=self.table_usage,
            status=Cart.Status.PENDING,
        )
        if items_data:
            for d in items_data:
                CartItem.objects.create(
                    cart=cart,
                    menu=d.get("menu"),
                    setmenu=d.get("setmenu"),
                    quantity=d["quantity"],
                    price_at_cart=d["price"],
                )
        return cart

    def _make_event(self, cart, total_price=None, event_id=None):
        total = total_price or sum(
            ci.price_at_cart * ci.quantity
            for ci in CartItem.objects.filter(cart=cart)
        )
        return {
            "event_id": event_id or str(uuid.uuid4()),
            "data": {
                "cart_id": cart.pk,
                "table_usage_id": self.table_usage.pk,
                "total_price": total,
                "original_total_price": total,
                "total_discount": 0,
                "status": "completed",
            },
        }

    def test_create_order_success(self):
        """정상 주문 생성"""
        cart = self._make_cart([
            {"menu": self.menu, "quantity": 2, "price": 5000},
        ])
        event_data = self._make_event(cart)

        OrderService.create_order_from_event(event_data)

        # Order 생성 확인
        order = Order.objects.get(cart=cart)
        assert order.order_price == 10000
        assert order.order_status == "PAID"

        # OrderItem 생성 확인
        items = OrderItem.objects.filter(order=order)
        assert items.count() == 1
        assert items.first().quantity == 2

        # Cart 상태 확인
        cart.refresh_from_db()
        assert cart.status == Cart.Status.ORDERED

        # TableUsage 누적 금액 확인
        self.table_usage.refresh_from_db()
        assert self.table_usage.accumulated_amount == 10000

        # 재고 차감 확인
        self.menu.refresh_from_db()
        assert self.menu.stock == 48  # 50 - 2

    def test_create_order_with_setmenu(self):
        """세트메뉴 주문 → 부모 + 자식 OrderItem + 구성품 재고 차감"""
        menu1 = self._create_menu(self.booth, name="사이다", stock=30)
        menu2 = self._create_menu(self.booth, name="핫도그", stock=30)
        setmenu = self._create_set_menu(
            self.booth, name="세트B", price=8000,
            menus=[(menu1, 1), (menu2, 2)],
        )

        cart = self._make_cart([
            {"setmenu": setmenu, "menu": None, "quantity": 1, "price": 8000},
        ])
        event_data = self._make_event(cart, total_price=8000)

        OrderService.create_order_from_event(event_data)

        order = Order.objects.get(cart=cart)
        # 부모 1개 + 자식 2개 = 3개
        assert OrderItem.objects.filter(order=order).count() == 3

        parent = OrderItem.objects.get(order=order, parent__isnull=True)
        assert parent.setmenu == setmenu
        assert parent.quantity == 1

        children = OrderItem.objects.filter(order=order, parent=parent)
        assert children.count() == 2

        menu1.refresh_from_db()
        assert menu1.stock == 29  # 30 - 1*1

        menu2.refresh_from_db()
        assert menu2.stock == 28  # 30 - 1*2

    def test_duplicate_event_id(self):
        """중복 event_id → 무시"""
        cart = self._make_cart([
            {"menu": self.menu, "quantity": 1, "price": 5000},
        ])
        event_id = str(uuid.uuid4())
        event_data = self._make_event(cart, event_id=event_id)

        OrderService.create_order_from_event(event_data)
        # 두 번째 호출
        result = OrderService.create_order_from_event(event_data)

        assert result["result"] == "duplicate_event"
        assert Order.objects.count() == 1

    def test_duplicate_cart_id(self):
        """동일 cart_id로 재요청 → 무시"""
        cart = self._make_cart([
            {"menu": self.menu, "quantity": 1, "price": 5000},
        ])
        event1 = self._make_event(cart)
        OrderService.create_order_from_event(event1)

        event2 = self._make_event(cart, event_id=str(uuid.uuid4()))
        result = OrderService.create_order_from_event(event2)

        assert result["result"] == "duplicate_cart"

    def test_invalid_status(self):
        """status != completed → 무시"""
        cart = self._make_cart([
            {"menu": self.menu, "quantity": 1, "price": 5000},
        ])
        event_data = self._make_event(cart)
        event_data["data"]["status"] = "pending"

        result = OrderService.create_order_from_event(event_data)

        assert result["result"] == "invalid_status"


# ═════════════════════════════════════════════
# OrderService.handle_serving_event 테스트
# ═════════════════════════════════════════════

@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class HandleServingEventTest(TransactionTestCase, OrderTestMixin):

    def setUp(self):
        self.user, self.booth, self.table, self.table_usage = (
            self._create_booth_and_table()
        )
        self.menu = self._create_menu(self.booth)
        self.booth_id = self.booth.pk

    def test_serving_status(self):
        """serving 이벤트 → SERVING"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000, "status": "COOKED"}],
        )

        result = OrderService.handle_serving_event(
            {"order_item_id": item.pk, "status": "serving"},
            action="serving",
        )

        assert result["result"] == "success"
        assert result["status"] == "SERVING"

        item.refresh_from_db()
        assert item.status == "SERVING"

    def test_served_status(self):
        """served 이벤트 → SERVED + served_at"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000, "status": "SERVING"}],
        )

        result = OrderService.handle_serving_event(
            {"order_item_id": item.pk, "status": "served"},
            action="served",
        )

        assert result["result"] == "success"

        item.refresh_from_db()
        assert item.status == "SERVED"
        assert item.served_at is not None

    def test_served_all_completes_order(self):
        """전체 served → Order COMPLETED"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000, "status": "SERVING"}],
        )

        OrderService.handle_serving_event(
            {"order_item_id": item.pk, "status": "served"},
            action="served",
        )

        order.refresh_from_db()
        assert order.order_status == "COMPLETED"

    def test_not_found(self):
        result = OrderService.handle_serving_event(
            {"order_item_id": 99999}, action="serving"
        )
        assert result["result"] == "not_found"

    def test_missing_order_item_id(self):
        result = OrderService.handle_serving_event({}, action="serving")
        assert result["result"] == "missing_order_item_id"

    def test_setmenu_parent_blocked(self):
        """세트메뉴 부모 → invalid_target"""
        setmenu = self._create_set_menu(self.booth)
        order, [parent] = self._create_order_with_items(
            self.table_usage,
            [{"setmenu": setmenu, "quantity": 1, "fixed_price": 12000, "status": "COOKED"}],
        )

        result = OrderService.handle_serving_event(
            {"order_item_id": parent.pk}, action="serving"
        )

        assert result["result"] == "invalid_target"


# ═════════════════════════════════════════════
# OrderService.handle_payment_rejected_event 테스트
# ═════════════════════════════════════════════

@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class HandlePaymentRejectedTest(TransactionTestCase, OrderTestMixin):

    def setUp(self):
        self.user, self.booth, self.table, self.table_usage = (
            self._create_booth_and_table()
        )
        self.booth_id = self.booth.pk

    def test_success_restores_cart(self):
        """정상: Cart pending → active 복구"""
        cart = Cart.objects.create(
            table_usage=self.table_usage,
            status=Cart.Status.PENDING,
        )

        result = OrderService.handle_payment_rejected_event({
            "data": {
                "cart_id": cart.pk,
                "table_usage_id": self.table_usage.pk,
            }
        })

        assert result["result"] == "success"

        cart.refresh_from_db()
        assert cart.status == Cart.Status.ACTIVE

    def test_order_already_exists(self):
        """이미 Order가 존재하면 무시"""
        cart = Cart.objects.create(
            table_usage=self.table_usage,
            status=Cart.Status.ORDERED,
        )
        Order.objects.create(
            table_usage=self.table_usage,
            cart=cart,
            order_price=5000, original_price=5000, order_status="PAID",
        )

        result = OrderService.handle_payment_rejected_event({
            "data": {"cart_id": cart.pk}
        })

        assert result["result"] == "order_already_exists"

    def test_cart_not_found(self):
        result = OrderService.handle_payment_rejected_event({
            "data": {"cart_id": 99999}
        })
        assert result["result"] == "cart_not_found"

    def test_not_pending(self):
        """Cart가 pending이 아닌 경우"""
        cart = Cart.objects.create(
            table_usage=self.table_usage,
            status=Cart.Status.ACTIVE,
        )

        result = OrderService.handle_payment_rejected_event({
            "data": {"cart_id": cart.pk}
        })

        assert result["result"] == "not_pending"


# ═════════════════════════════════════════════
# REST API 테스트
# ═════════════════════════════════════════════

@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class OrderItemStatusUpdateAPITest(TransactionTestCase, OrderTestMixin):
    """PATCH /api/v3/django/order/status/"""

    def setUp(self):
        self.user, self.booth, self.table, self.table_usage = (
            self._create_booth_and_table()
        )
        self.menu = self._create_menu(self.booth)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v3/django/order/status/"

    @patch("core.redis_client.publish")
    def test_patch_success(self, mock_pub):
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000}],
        )

        resp = self.client.patch(
            self.url,
            {"order_item_id": item.pk, "target_status": "COOKED"},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["data"]["status"] == "COOKED"

    def test_patch_missing_fields(self):
        resp = self.client.patch(self.url, {}, format="json")
        assert resp.status_code == 400

    def test_patch_unauthenticated(self):
        client = APIClient()
        resp = client.patch(
            self.url, {"order_item_id": 1, "target_status": "COOKED"}, format="json"
        )
        assert resp.status_code in (401, 403)

    @patch("core.redis_client.publish")
    def test_patch_not_found(self, mock_pub):
        resp = self.client.patch(
            self.url,
            {"order_item_id": 99999, "target_status": "COOKED"},
            format="json",
        )
        assert resp.status_code == 404


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class OrderItemCancelAPITest(TransactionTestCase, OrderTestMixin):
    """PATCH /api/v3/django/order/<id>/cancel/"""

    def setUp(self):
        self.user, self.booth, self.table, self.table_usage = (
            self._create_booth_and_table()
        )
        self.menu = self._create_menu(self.booth, stock=100)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("core.redis_client.publish")
    def test_cancel_success(self, mock_pub):
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 3, "fixed_price": 5000}],
        )
        self.table_usage.accumulated_amount = 15000
        self.table_usage.save()

        resp = self.client.patch(
            f"/api/v3/django/order/{item.pk}/cancel/",
            {"cancel_quantity": 1},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["data"]["remaining_quantity"] == 2
        assert resp.data["data"]["refund_amount"] == 5000

    def test_cancel_missing_quantity(self):
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000}],
        )

        resp = self.client.patch(
            f"/api/v3/django/order/{item.pk}/cancel/",
            {},
            format="json",
        )

        assert resp.status_code == 400

    def test_cancel_unauthenticated(self):
        client = APIClient()
        resp = client.patch(
            "/api/v3/django/order/1/cancel/",
            {"cancel_quantity": 1},
            format="json",
        )
        assert resp.status_code in (401, 403)


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class TableOrderHistoryAPITest(TransactionTestCase, OrderTestMixin):
    """GET /api/v3/django/order/table/<table_usage_id>/"""

    def setUp(self):
        self.user, self.booth, self.table, self.table_usage = (
            self._create_booth_and_table()
        )
        self.menu = self._create_menu(self.booth)
        self.client = APIClient()

    def test_get_order_history(self):
        """주문 내역 정상 조회 (인증 불필요)"""
        order, [item] = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 2, "fixed_price": 5000}],
        )

        resp = self.client.get(
            f"/api/v3/django/order/table/{self.table_usage.pk}/"
        )

        assert resp.status_code == 200
        data = resp.data["data"]
        assert data["table_usage_id"] == self.table_usage.pk
        assert data["table_number"] == "1"
        assert len(data["order_list"]) == 1
        assert data["order_list"][0]["order_id"] == order.pk
        assert len(data["order_list"][0]["order_items"]) == 1
        assert data["table_total_price"] == 10000

    def test_get_excludes_cancelled(self):
        """CANCELLED 주문은 제외"""
        order, _ = self._create_order_with_items(
            self.table_usage,
            [{"menu": self.menu, "quantity": 1, "fixed_price": 5000}],
        )
        order.order_status = "CANCELLED"
        order.save()

        resp = self.client.get(
            f"/api/v3/django/order/table/{self.table_usage.pk}/"
        )

        assert resp.status_code == 200
        assert len(resp.data["data"]["order_list"]) == 0

    def test_ended_session_forbidden(self):
        """종료된 세션 → 403"""
        self.table_usage.ended_at = timezone.now()
        self.table_usage.save()

        resp = self.client.get(
            f"/api/v3/django/order/table/{self.table_usage.pk}/"
        )

        assert resp.status_code == 403

    def test_not_found(self):
        resp = self.client.get("/api/v3/django/order/table/99999/")
        assert resp.status_code == 404

    def test_setmenu_shown_as_set_unit(self):
        """세트메뉴 → 세트 단위로 표시 (자식 미노출)"""
        setmenu = self._create_set_menu(self.booth, name="세트C", price=10000)
        order = Order.objects.create(
            table_usage=self.table_usage,
            order_price=10000, original_price=10000, order_status="PAID",
        )
        parent = OrderItem.objects.create(
            order=order, setmenu=setmenu, quantity=1,
            fixed_price=10000, status="COOKING",
        )
        child = OrderItem.objects.create(
            order=order, menu=self.menu, parent=parent,
            quantity=1, fixed_price=0, status="COOKING",
        )

        resp = self.client.get(
            f"/api/v3/django/order/table/{self.table_usage.pk}/"
        )

        assert resp.status_code == 200
        order_items = resp.data["data"]["order_list"][0]["order_items"]
        # 부모 아이템만 표시 (자식 제외)
        assert len(order_items) == 1
        assert order_items[0]["name"] == "세트C"
        assert order_items[0]["from_set"] is True

    def test_multiple_orders(self):
        """여러 주문이 order_list에 모두 포함"""
        for i in range(3):
            self._create_order_with_items(
                self.table_usage,
                [{"menu": self.menu, "quantity": 1, "fixed_price": 1000 * (i + 1)}],
            )

        resp = self.client.get(
            f"/api/v3/django/order/table/{self.table_usage.pk}/"
        )

        assert resp.status_code == 200
        assert len(resp.data["data"]["order_list"]) == 3
        assert resp.data["data"]["table_total_price"] == 1000 + 2000 + 3000
