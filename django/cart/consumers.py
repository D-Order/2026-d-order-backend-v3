import asyncio
import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone

from core.mixins import KoreanAsyncJsonMixin
from table.models import TableUsage
from .services_ws import build_cart_snapshot_data


logger = logging.getLogger(__name__)


class CustomerCartConsumer(KoreanAsyncJsonMixin, AsyncJsonWebsocketConsumer):
    """
    손님용 실시간 장바구니 WebSocket Consumer
    """

    HEARTBEAT_INTERVAL_SECONDS = 25

    async def connect(self):
        self.table_usage_id = self.scope["url_route"]["kwargs"]["table_usage_id"]
        self.group_name = f"table_usage_{self.table_usage_id}.cart"
        self.heartbeat_task = None

        validation = await self._validate_table_usage()

        if not validation["is_valid"]:

            await self.accept()

            await self.send_json({
                "type": "ERROR",
                "timestamp": timezone.localtime().isoformat(),
                "message": validation["message"],
                "data": {
                    "error_code": validation["error_code"],
                    "table_usage_id": self.table_usage_id,
                },
            })

            await self.close(code=4004)
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

        logger.info(f"[CartWS] CONNECT: {self.channel_name}, table_usage_id={self.table_usage_id}")

        await self.send_json({
            "type": "SUBSCRIBED",
            "timestamp": timezone.localtime().isoformat(),
            "message": "장바구니 웹소켓 구독이 완료되었습니다.",
            "data": {
                "table_usage_id": int(self.table_usage_id),
            },
        })

        await self.send_cart_snapshot()

        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, close_code):
        logger.info(
            f"[CartWS] DISCONNECT: {self.channel_name}, "
            f"table_usage_id={getattr(self, 'table_usage_id', None)}, code={close_code}"
        )

        if getattr(self, "heartbeat_task", None):
            self.heartbeat_task.cancel()

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, content):
        message_type = content.get("type")

        if message_type == "PING":
            await self.send_json({
                "type": "PONG",
                "timestamp": timezone.localtime().isoformat(),
                "message": "heartbeat",
                "data": None,
            })
            return

        if message_type == "PONG":
            return

        await self.send_json({
            "type": "ERROR",
            "timestamp": timezone.localtime().isoformat(),
            "message": "메세지 수신을 지원하지 않습니다. REST API를 사용하세요.",
            "data": {
                "error_code": "UNSUPPORTED_MESSAGE_TYPE",
                "received_type": message_type,
            },
        })

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL_SECONDS)

                await self.send_json({
                    "type": "PONG",
                    "timestamp": timezone.localtime().isoformat(),
                    "message": "heartbeat",
                    "data": None,
                })

        except asyncio.CancelledError:
            return

        except Exception as e:
            logger.warning(
                f"[CartWS] heartbeat failed: table_usage_id={self.table_usage_id}, error={e}"
            )

    async def _validate_table_usage(self):
        def _query():
            try:
                table_usage = (
                    TableUsage.objects
                    .select_related("table", "table__booth")
                    .get(id=self.table_usage_id)
                )

                if table_usage.ended_at is not None:
                    return {
                        "is_valid": False,
                        "error_code": "TABLE_USAGE_ENDED",
                        "message": "이미 종료된 테이블 세션입니다.",
                    }

                return {
                    "is_valid": True,
                    "error_code": None,
                    "message": "OK",
                }

            except TableUsage.DoesNotExist:
                return {
                    "is_valid": False,
                    "error_code": "TABLE_USAGE_NOT_FOUND",
                    "message": "존재하지 않는 테이블 세션입니다.",
                }

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
        return await sync_to_async(build_cart_snapshot_data)(
            self.table_usage_id
        )