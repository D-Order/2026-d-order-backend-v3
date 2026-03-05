from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.db.models import Sum, F, Value, CharField, Prefetch
from django.db.models.functions import Coalesce
from django.utils import timezone
from asgiref.sync import sync_to_async
from order.models import Order, OrderItem
from core.mixins import KoreanAsyncJsonMixin
import logging

logger = logging.getLogger(__name__)


class AdminOrderManagementConsumer(KoreanAsyncJsonMixin, AsyncJsonWebsocketConsumer):
    """
    실시간 주문 관리 WebSocket Consumer

    그룹: booth_{booth_id}.order

    이벤트 타입:
      ① ADMIN_ORDER_SNAPSHOT  – 최초 연결 시 전체 주문 스냅샷
      ② ADMIN_NEW_ORDER       – 새 주문 알림 (Redis → Spring → Django)
      ③ ADMIN_ORDER_UPDATE    – 아이템 상태 변경
      ④ ADMIN_ORDER_CANCELLED – 주문 취소
      ⑤ ORDER_COMPLETED       – 전체 서빙 완료
      ⑥ MENU_AGGREGATION      – 메뉴별 실시간 집계
    """

    # ───────────────────────────────────────────
    # 연결 / 해제 / 수신
    # ───────────────────────────────────────────
    async def connect(self):
        self.booth_id = await self._authenticate()
        if self.booth_id is None:
            return

        self.group_name = f"booth_{self.booth_id}.order"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(f"[Order WS] 연결됨: {self.group_name}")
        await self.send_order_snapshot()
        await self.send_menu_aggregation()

    async def _authenticate(self):
        """JWT 쿠키 인증 → booth_id 반환, 실패 시 None"""
        user = self.scope.get("user")

        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return None

        try:
            booth = await sync_to_async(lambda: user.booth)()
            return booth.pk
        except Exception as e:
            logger.warning(f"[Order WS] User {user.username} has no booth: {e}")
            await self.close(code=4003)
            return None

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f"[Order WS] 연결 해제: {self.group_name} (code: {close_code})")

    async def receive_json(self, content):
        await self.send_json({
            "type": "error",
            "timestamp": timezone.now().isoformat(),
            "message": "메세지 수신을 지원하지 않습니다. REST API를 사용하세요.",
            "data": None,
        })

    # ───────────────────────────────────────────
    # ① ADMIN_ORDER_SNAPSHOT
    # ───────────────────────────────────────────
    async def send_order_snapshot(self):
        """현재 부스의 PAID 주문을 created_at 오름차순으로 직렬화하여 전송"""
        orders = await self._get_active_orders()
        serialized_orders = []
        for order in orders:
            serialized_orders.append(await self._serialize_order(order))

        total_sales = await self._get_total_sales()

        await self.send_json({
            "type": "ADMIN_ORDER_SNAPSHOT",
            "timestamp": timezone.localtime().isoformat(),
            "data": {
                # "total_sales": total_sales,
                "orders": serialized_orders,
            },
        })

    # ───────────────────────────────────────────
    # ② ADMIN_NEW_ORDER (group_send handler)
    # ───────────────────────────────────────────
    async def admin_new_order(self, event):
        """
        OrderService.create_order_from_event 에서 group_send 로 호출.
        event["data"]["order_id"] 로 DB에서 직접 조회 후 직렬화.
        """
        data = event.get("data", {})
        order_id = data.get("order_id")

        if order_id:
            order = await sync_to_async(
                lambda: Order.objects
                .filter(pk=order_id)
                .select_related("table_usage__table")
                .first()
            )()
            if order:
                serialized = await self._serialize_order(order)
                total_sales = await self._get_total_sales()
                await self.send_json({
                    "type": "ADMIN_NEW_ORDER",
                    "timestamp": timezone.localtime().isoformat(),
                    "data": {
                        "total_sales": total_sales,
                        "orders": [serialized],
                    },
                })
                await self.send_menu_aggregation()
                return

        # order_id 가 없거나 조회 실패 시 빈 배열
        total_sales = await self._get_total_sales()
        await self.send_json({
            "type": "ADMIN_NEW_ORDER",
            "timestamp": timezone.localtime().isoformat(),
            "data": {
                "total_sales": total_sales,
                "orders": [],
            },
        })

    # ───────────────────────────────────────────
    # ③ ADMIN_ORDER_UPDATE (group_send handler)
    # ───────────────────────────────────────────
    async def admin_order_update(self, event):
        data = event.get("data", {})
        await self.send_json({
            "type": "ADMIN_ORDER_UPDATE",
            "data": {
                "order_id": data.get("order_id"),
                "items": data.get("items", []),
            },
        })
        await self.send_menu_aggregation()

    # ───────────────────────────────────────────
    # ④ ADMIN_ORDER_CANCELLED (group_send handler)
    # ───────────────────────────────────────────
    async def admin_order_cancelled(self, event):
        data = event.get("data", {})
        await self.send_json({
            "type": "ADMIN_ORDER_CANCELLED",
            "data": {
                "order_id": data.get("order_id"),
                "item_id": data.get("item_id"),
                "refund_amount": data.get("refund_amount"),
                "new_total_sales": data.get("new_total_sales"),
            },
        })
        await self.send_menu_aggregation()

    # ───────────────────────────────────────────
    # ⑤ ORDER_COMPLETED (group_send handler)
    # ───────────────────────────────────────────
    async def admin_order_completed(self, event):
        data = event.get("data", {})
        updated_at = data.get("updated_at", timezone.localtime().isoformat())
        await self.send_json({
            "type": "ORDER_COMPLETED",
            "timestamp": updated_at,
            "data": {
                "order_id": data.get("order_id"),
                "table_num": data.get("table_num"),
                "table_usage_id": data.get("table_usage_id"),
                "order_status": data.get("order_status", "COMPLETED"),
                "updated_at": updated_at,
            },
        })

    # ───────────────────────────────────────────
    # ⑥ MENU_AGGREGATION
    # ───────────────────────────────────────────
    async def send_menu_aggregation(self):
        """
        현재 부스의 조리/서빙 대상 메뉴별 수량 집계.
        status가 COOKING, COOKED, SERVING인 것만 대상.
        음식(MENU) / 음료(DRINK)로 분류, 수량 내림차순 → 이름 오름차순.
        """
        aggregation = await self._get_menu_aggregation()
        await self.send_json({
            "type": "MENU_AGGREGATION",
            "data": aggregation,
        })

    async def admin_menu_aggregation(self, event):
        """group_send 핸들러: 외부에서 집계 갱신 트리거 시"""
        await self.send_menu_aggregation()

    # ───────────────────────────────────────────
    # Private: DB 조회 / 직렬화
    # ───────────────────────────────────────────
    async def _get_active_orders(self):
        """해당 부스의 PAID 상태 주문을 오래된 순으로 조회"""
        return await sync_to_async(list)(
            Order.objects
            .filter(
                order_status="PAID",
                table_usage__table__booth_id=self.booth_id,
            )
            .select_related("table_usage__table")
            .order_by("created_at")
        )

    async def _get_menu_aggregation(self):
        """
        DB에서 메뉴별 수량 집계 조회.
        리프 아이템만 대상 (세트메뉴 부모 제외, 자식 OrderItem + 일반 메뉴).
        status가 COOKING, COOKED, SERVING인 것만 대상.
        """
        active_statuses = ["COOKING", "COOKED", "SERVING"]

        def _query():
            # 리프 아이템: menu가 있고, 세트메뉴 부모(parent=None, setmenu≠None)가 아닌 것
            qs = (
                OrderItem.objects
                .filter(
                    order__order_status="PAID",
                    order__table_usage__table__booth_id=self.booth_id,
                    status__in=active_statuses,
                    menu__isnull=False,
                )
                .exclude(parent__isnull=True, setmenu__isnull=False)
                .select_related("menu")
            )

            food_map = {}
            drink_map = {}

            for item in qs:
                name = item.menu.name
                category = item.menu.category
                target = drink_map if category == "DRINK" else food_map
                target[name] = target.get(name, 0) + item.quantity

            def sort_key(pair):
                return (-pair[1], pair[0])

            food_summary = [
                {"menu_name": k, "total_quantity": v}
                for k, v in sorted(food_map.items(), key=sort_key)
            ]
            beverage_summary = [
                {"menu_name": k, "total_quantity": v}
                for k, v in sorted(drink_map.items(), key=sort_key)
            ]

            return {
                "food_summary": food_summary,
                "beverage_summary": beverage_summary,
            }

        return await sync_to_async(_query)()

    async def _get_total_sales(self):
        """해당 부스의 전체 주문(PAID + COMPLETED) 총 매출 합산"""
        def _query():
            return (
                Order.objects
                .filter(
                    order_status__in=["PAID", "COMPLETED"],
                    table_usage__table__booth_id=self.booth_id,
                )
                .aggregate(total=Sum("order_price"))["total"]
            ) or 0
        return await sync_to_async(_query)()

    # ───────────────────────────────────────────
    # ⑦ TOTAL_SALES_UPDATE (group_send handler)
    # ───────────────────────────────────────────
    async def total_sales_update(self, event):
        """총매출 갱신 이벤트 수신 → 매출 consumer에 위임하지 않고 직접 무시"""
        pass

    async def _serialize_order(self, order):
        """Order 객체 → API 스펙 JSON (세트메뉴는 자식 OrderItem 개별 조회)"""
        def _query():
            table_usage = order.table_usage
            table = table_usage.table
            table_num = table.table_num

            # 상위 아이템 조회 + 세트메뉴 자식 프리페치
            top_items = list(
                order.items
                .filter(parent__isnull=True)
                .select_related("menu", "setmenu")
                .prefetch_related(
                    Prefetch("children", queryset=OrderItem.objects.select_related("menu"))
                )
            )

            items = []
            for item in top_items:
                if item.setmenu_id:
                    # 세트메뉴 → 자식 OrderItem 개별 직렬화
                    set_menu_name = item.setmenu.name
                    for child in item.children.all():
                        menu_name = child.menu.name if child.menu else "알 수 없음"
                        image = child.menu.image.url if child.menu and child.menu.image else None
                        items.append({
                            "order_item_id": child.id,
                            "menu_name": menu_name,
                            "image": image,
                            "quantity": child.quantity,
                            "fixed_price": item.fixed_price,
                            "item_total_price": item.fixed_price * item.quantity,
                            "status": child.status,
                            "is_set": True,
                            "set_menu_name": set_menu_name,
                            "parent_order_item_id": item.id,
                        })
                else:
                    # 일반 메뉴
                    menu_name = item.menu.name if item.menu else "알 수 없음"
                    image = item.menu.image.url if item.menu and item.menu.image else None
                    item_total_price = item.fixed_price * item.quantity
                    items.append({
                        "order_item_id": item.id,
                        "menu_name": menu_name,
                        "image": image,
                        "quantity": item.quantity,
                        "fixed_price": item.fixed_price,
                        "item_total_price": item_total_price,
                        "status": item.status,
                        "is_set": False,
                    })

            diff = timezone.now() - order.created_at
            minutes = int(diff.total_seconds() // 60)
            time_ago = f"{minutes}분 전"
            has_coupon = order.coupon_id is not None

            return {
                "order_id": order.id,
                "table_num": table_num,
                "table_usage_id": order.table_usage_id,
                "order_status": order.order_status,
                "time_ago": time_ago,
                "has_coupon": has_coupon,
                "items": items,
            }

        return await sync_to_async(_query)()


class BoothSalesConsumer(KoreanAsyncJsonMixin, AsyncJsonWebsocketConsumer):
    """
    부스 총매출 실시간 WebSocket Consumer

    그룹: booth_{booth_id}.order (주문 관리 consumer와 같은 그룹 공유)

    이벤트 타입:
      ① TOTAL_SALES_SNAPSHOT  – 최초 연결 시 총매출
      ② TOTAL_SALES_UPDATE    – 주문 생성/취소 시 갱신
    """

    async def connect(self):
        self.booth_id = await self._authenticate()
        if self.booth_id is None:
            return

        self.group_name = f"booth_{self.booth_id}.order"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(f"[Sales WS] 연결됨: {self.group_name}")
        await self._send_sales_snapshot()

    async def _authenticate(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return None
        try:
            booth = await sync_to_async(lambda: user.booth)()
            return booth.pk
        except Exception as e:
            logger.warning(f"[Sales WS] User {user.username} has no booth: {e}")
            await self.close(code=4003)
            return None

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f"[Sales WS] 연결 해제: {self.group_name} (code: {close_code})")

    async def receive_json(self, content):
        await self.send_json({
            "type": "error",
            "message": "메세지 수신을 지원하지 않습니다.",
        })

    # ① TOTAL_SALES_SNAPSHOT
    async def _send_sales_snapshot(self):
        total_sales = await self._get_total_sales()
        await self.send_json({
            "type": "TOTAL_SALES_SNAPSHOT",
            "timestamp": timezone.localtime().isoformat(),
            "data": {
                "total_sales": total_sales,
            },
        })

    # ② TOTAL_SALES_UPDATE (group_send handler)
    async def total_sales_update(self, event):
        total_sales = await self._get_total_sales()
        await self.send_json({
            "type": "TOTAL_SALES_UPDATE",
            "timestamp": timezone.localtime().isoformat(),
            "data": {
                "total_sales": total_sales,
            },
        })

    # 주문관리 consumer의 group_send 핸들러 - 이 consumer에선 무시
    async def admin_new_order(self, event):
        pass

    async def admin_order_update(self, event):
        pass

    async def admin_order_cancelled(self, event):
        pass

    async def admin_order_completed(self, event):
        pass

    async def admin_menu_aggregation(self, event):
        pass

    async def _get_total_sales(self):
        """부스의 전체 주문(PAID + COMPLETED) 총 매출(order_price 합산)"""
        def _query():
            return (
                Order.objects
                .filter(
                    order_status__in=["PAID", "COMPLETED"],
                    table_usage__table__booth_id=self.booth_id,
                )
                .aggregate(total=Sum("order_price"))["total"]
            ) or 0
        return await sync_to_async(_query)()

