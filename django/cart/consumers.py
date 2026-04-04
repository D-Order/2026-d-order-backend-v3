from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone

from core.mixins import KoreanAsyncJsonMixin
from table.models import TableUsage
from .models import Cart, CartItem
from .services import *
from .services_ws import *


class CustomerCartConsumer(KoreanAsyncJsonMixin, AsyncJsonWebsocketConsumer):
    """
    손님용 실시간 장바구니 WebSocket Consumer

    그룹: table_usage_{table_usage_id}.cart

    이벤트 타입:
    ① CART_SNAPSHOT
    ② CART_UPDATED
    ③ CART_ITEM_ADDED
    ④ CART_ITEM_UPDATED
    ⑤ CART_ITEM_DELETED
    ⑥ CART_COUPON_APPLIED
    ⑦ CART_COUPON_CANCELLED
    ⑧ CART_PAYMENT_PENDING
    ⑨ CART_RESET
    """

    async def connect(self):
        self.table_usage_id = self.scope["url_route"]["kwargs"]["table_usage_id"]

        is_valid = await self._validate_table_usage()
        if not is_valid:
            await self.close(code=4004)
            return

        self.group_name = f"table_usage_{self.table_usage_id}.cart"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send_cart_snapshot()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        await self.send_json({
            "type": "ERROR",
            "timestamp": timezone.localtime().isoformat(),
            "message": "메세지 수신을 지원하지 않습니다. REST API를 사용하세요.",
            "data": None,
        })

    async def _validate_table_usage(self):
        def _query():
            try:
                table_usage = TableUsage.objects.select_related("table", "table__booth").get(
                    id=self.table_usage_id
                )
                return table_usage.ended_at is None
            except TableUsage.DoesNotExist:
                return False

        return await sync_to_async(_query)()

    async def send_cart_snapshot(self):
        payload = await self._build_cart_payload()
        await self.send_json({
            "type": "CART_SNAPSHOT",
            "timestamp": timezone.localtime().isoformat(),
            "data": payload,
        })

    async def cart_updated(self, event):
        await self.send_json({
            "type": event.get("event_type", "CART_UPDATED"),
            "timestamp": timezone.localtime().isoformat(),
            "message": event.get("message", "장바구니가 변경되었습니다."),
            "data": event.get("data"),
        })

    async def _build_cart_payload(self):
        return await sync_to_async(build_cart_snapshot_data)(self.table_usage_id)