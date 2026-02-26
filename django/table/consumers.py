from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from asgiref.sync import sync_to_async
from .ws_handlers import TableMixin
import logging

logger = logging.getLogger(__name__)


class TableConsumer(TableMixin,AsyncJsonWebsocketConsumer):
    """부스 테이블 관리 WebSocket Consumer

    인증: JWTWebSocketMiddleware에서 처리 (scope["user"] 설정됨)
    그룹: booth_{booth_id}.tables
    """

    async def connect(self):
        """WebSocket 연결 처리"""
        # JWT 인증 확인
        user = self.scope.get("user")
        
        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)  # Unauthorized
            return

        # 부스 확인
        try:
            booth = await sync_to_async(lambda: user.booth)()
            self.booth_id = booth.pk
        except Exception as e:
            logger.warning(f"User {user.username} has no booth: {e}")
            await self.close(code=4003)  # Forbidden - No booth
            return

        # 부스 그룹명 생성
        self.group_name = f'booth_{self.booth_id}.tables'

        # 그룹 구독
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # 연결 수락
        await self.accept()

        logger.info(f'WebSocket 연결됨: User {user.username} connected to {self.group_name}')

        # 연결 확인 메시지 전송
        await self.send_json({
            'type': 'connection_established',
            'booth_id': self.booth_id,
            'message': f'부스 {self.booth_id} 테이블 채널에 연결되었습니다.'
        })

    async def disconnect(self, close_code):
        """WebSocket 연결 해제"""
        # 그룹 구독 해제
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f'WebSocket 연결 해제: {self.group_name} (code: {close_code})')

    async def receive_json(self, content):
        """클라이언트로부터 메시지 수신

        테이블 관리는 REST API를 통해 처리
        WebSocket은 서버 -> 클라이언트 단방향 전송만 사용합니다.
        c -> S 요청 거부임
        """
        await self.send_json({
            'type': 'error',
            'message': '메세지 안 받아요. REST API를 사용하세요.'
        })