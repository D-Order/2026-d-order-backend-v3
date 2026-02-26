from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from asgiref.sync import sync_to_async
from .ws_handlers import TableMixin, TableDetailMixin
import logging

from core.mixins import KoreanAsyncJsonMixin
logger = logging.getLogger(__name__)



class BaseTableConsumer(KoreanAsyncJsonMixin, AsyncJsonWebsocketConsumer):
    """테이블 Consumer 공통 기반"""

    async def _authenticate(self):
        """WebSocket 연결 처리"""
        # JWT 인증 확인
        user = self.scope.get("user")

        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return None

        try:
            booth = await sync_to_async(lambda: user.booth)()
            return booth.pk
        except Exception as e:
            logger.warning(f"User {user.username} has no booth: {e}")
            await self.close(code=4003)
            return None

    async def receive_json(self, content):
        await self.send_json({
            'type': 'error',
            'timestamp': timezone.now().isoformat(),
            'message': '메세지 안 받아요. REST API를 사용하세요.',
            'data': None
        })


class TableConsumer(TableMixin, BaseTableConsumer):
    """부스 테이블 목록 WebSocket Consumer

    그룹: booth_{booth_id}.tables
    """

    async def connect(self):
        self.booth_id = await self._authenticate()
        if self.booth_id is None:
            return

        self.group_name = f'booth_{self.booth_id}.tables'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(f'WebSocket 연결됨: {self.group_name}')

        await self.send_json({
            'type': 'connection_established',
            'timestamp': timezone.now().isoformat(),
            'message': f'부스 {self.booth_id} 테이블 채널에 연결되었습니다.',
            'data': {
                'booth_id': self.booth_id
            }
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f'WebSocket 연결 해제: {self.group_name} (code: {close_code})')


class TableDetailConsumer(TableDetailMixin, BaseTableConsumer):
    """특정 테이블 상세 WebSocket Consumer

    그룹: booth_{booth_id}.tables.{table_num}
    """

    async def connect(self):
        self.booth_id = await self._authenticate()
        if self.booth_id is None:
            return

        self.table_num = self.scope['url_route']['kwargs']['table_num']
        self.group_name = f'booth_{self.booth_id}.tables.{self.table_num}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(f'WebSocket 연결됨: {self.group_name}')

        await self.send_json({
            'type': 'connection_established',
            'timestamp': timezone.now().isoformat(),
            'message': f'부스 {self.booth_id} {self.table_num}번 테이블 채널에 연결되었습니다.',
            'data': {
                'booth_id': self.booth_id,
                'table_num': self.table_num
            }
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f'WebSocket 연결 해제: {self.group_name} (code: {close_code})')
