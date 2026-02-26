import logging
from django.test import override_settings, TransactionTestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from channels.layers import get_channel_layer
from django.urls import re_path
from asgiref.sync import sync_to_async
from booth.models import Booth
from table.models import Table, TableGroup, TableUsage
from table.consumers import TableConsumer
from table.services import TableService
from core.test_utils import IN_MEMORY_STORAGES, suppress_request_warnings

User = get_user_model()
logger = logging.getLogger(__name__)

SIGNUP_URL     = '/api/v3/django/auth/signup/'
TABLE_LIST_URL = '/api/v3/django/booth/tables/'
RESET_URL      = '/api/v3/django/booth/tables/reset/'
MERGE_URL      = '/api/v3/django/booth/tables/merge/'

VALID_SIGNUP_DATA = {
    "username": "testuser",
    "password": "testpass123",
    "booth_data": {
        "name": "테스트 부스",
        "table_max_cnt": 10,
        "account": "1234567890",
        "depositor": "홍길동",
        "bank": "신한은행",
        "seat_type": "NO",
        "seat_fee_person": 0,
        "seat_fee_table": 0,
        "table_limit_hours": 2.0
    }
}


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableListTestCase(APITestCase):
    """테이블 목록 조회 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.client.cookies.clear()

    def test_get_tables_success(self):
        """인증된 사용자 테이블 목록 조회"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TABLE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), VALID_SIGNUP_DATA['booth_data']['table_max_cnt'])

    def test_get_tables_fields(self):
        """응답 필드 구조 검증"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TABLE_LIST_URL)

        for table_data in response.data:
            self.assertIn('booth', table_data)
            self.assertIn('table_num', table_data)
            self.assertIn('status', table_data)
            self.assertIn('group', table_data)
            self.assertIn('total_revenue', table_data)
            self.assertIn('recent_3_orders', table_data)
            self.assertIn('started_at', table_data)
            self.assertEqual(table_data['booth'], self.booth.pk)

    def test_get_tables_initial_state(self):
        """초기 상태: 전부 AVAILABLE, group None, started_at None"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TABLE_LIST_URL)

        for table_data in response.data:
            self.assertEqual(table_data['status'], 'AVAILABLE')
            self.assertIsNone(table_data['group'])
            self.assertIsNone(table_data['started_at'])

    def test_get_tables_ordered_by_table_num(self):
        """table_num 오름차순 정렬 검증"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TABLE_LIST_URL)

        table_nums = [t['table_num'] for t in response.data]
        self.assertEqual(table_nums, sorted(table_nums))

    def test_get_tables_unauthorized(self):
        """인증 없이 조회 시 401"""
        response = self.client.get(TABLE_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableResetTestCase(APITestCase):
    """테이블 리셋 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.client.cookies.clear()

    def _set_tables_in_use(self, table_nums):
        """테이블 IN_USE 상태로 변경 + 사용 기록 생성"""
        tables = Table.objects.filter(booth=self.booth, table_num__in=table_nums)
        tables.update(status=Table.Status.IN_USE)
        for table in tables:
            TableUsage.objects.create(table=table, started_at=now())
        return tables

    def test_reset_tables_success(self):
        """일반 테이블 리셋 성공"""
        self.client.force_authenticate(user=self.user)
        self._set_tables_in_use([2, 3])

        response = self.client.post(RESET_URL, {'table_nums': [2, 3]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    def test_reset_tables_count(self):
        """리셋된 테이블 개수 반환 검증"""
        self.client.force_authenticate(user=self.user)
        self._set_tables_in_use([2, 3])

        response = self.client.post(RESET_URL, {'table_nums': [2, 3]}, format='json')

        self.assertEqual(response.data['data']['reset_table_cnt'], 2)

    def test_reset_tables_status(self):
        """리셋 후 테이블 상태 AVAILABLE 확인"""
        self.client.force_authenticate(user=self.user)
        tables = self._set_tables_in_use([2, 3])

        self.client.post(RESET_URL, {'table_nums': [2, 3]}, format='json')

        for table in tables:
            table.refresh_from_db()
            self.assertEqual(table.status, Table.Status.ACTIVE)

    def test_reset_tables_usage_ended(self):
        """리셋 후 사용 기록 종료 확인"""
        self.client.force_authenticate(user=self.user)
        tables = self._set_tables_in_use([2, 3])

        self.client.post(RESET_URL, {'table_nums': [2, 3]}, format='json')

        usages = TableUsage.objects.filter(table__in=tables)
        for usage in usages:
            self.assertIsNotNone(usage.ended_at)
            self.assertIsNotNone(usage.usage_minutes)

    def test_reset_merged_tables_status(self):
        """병합된 테이블 리셋 시 병합 그룹 전체 초기화"""
        self.client.force_authenticate(user=self.user)
        self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')
        self._set_tables_in_use([1])  # 요청 테이블은 IN_USE여야 리셋 가능

        response = self.client.post(RESET_URL, {'table_nums': [1]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for table_num in [1, 2, 3]:
            table = Table.objects.get(booth=self.booth, table_num=table_num)
            self.assertEqual(table.status, Table.Status.ACTIVE)
            self.assertIsNone(table.group)

    def test_reset_merged_tables_count(self):
        """병합된 테이블 리셋 시 count가 그룹 전체 수 반환"""
        self.client.force_authenticate(user=self.user)
        self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')
        self._set_tables_in_use([1])  # 요청 테이블은 IN_USE여야 리셋 가능

        response = self.client.post(RESET_URL, {'table_nums': [1]}, format='json')

        self.assertEqual(response.data['data']['reset_table_cnt'], 3)

    def test_reset_tables_empty_input(self):
        """빈 리스트 입력 시 400"""
        self.client.force_authenticate(user=self.user)

        with suppress_request_warnings():
            response = self.client.post(RESET_URL, {'table_nums': []}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_tables_not_found(self):
        """존재하지 않는 테이블 번호 리셋 시 404"""
        self.client.force_authenticate(user=self.user)

        with suppress_request_warnings():
            response = self.client.post(RESET_URL, {'table_nums': [9999]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reset_tables_unauthorized(self):
        """인증 없이 리셋 시 401"""
        with suppress_request_warnings():
            response = self.client.post(RESET_URL, {'table_nums': [1]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableMergeTestCase(APITestCase):
    """테이블 병합 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.client.cookies.clear()

    def test_merge_tables_success(self):
        """기본 병합 성공"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    def test_merge_tables_count(self):
        """병합 개수 반환 검증"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')

        self.assertEqual(response.data['data']['merge_table_cnt'], 3)

    def test_merge_tables_group_created(self):
        """병합 후 TableGroup 생성 확인"""
        self.client.force_authenticate(user=self.user)
        self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')

        self.assertEqual(TableGroup.objects.count(), 1)

    def test_merge_tables_representative(self):
        """대표 테이블은 가장 낮은 번호"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(MERGE_URL, {'table_nums': [3, 1, 2]}, format='json')

        group = TableGroup.objects.first()
        self.assertEqual(group.representative_table.table_num, 1)
        self.assertEqual(response.data['data']['representive_table_num'], group.representative_table.table_num)

    def test_merge_tables_same_group(self):
        """병합된 테이블들이 동일 그룹 소속"""
        self.client.force_authenticate(user=self.user)
        self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')

        group = TableGroup.objects.first()
        for table_num in [1, 2, 3]:
            table = Table.objects.get(booth=self.booth, table_num=table_num)
            self.assertEqual(table.group, group)

    def test_merge_groups_into_one(self):
        """병합 그룹끼리 재병합 시 단일 그룹으로 통합"""
        self.client.force_authenticate(user=self.user)
        self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')
        self.client.post(MERGE_URL, {'table_nums': [4, 5, 6]}, format='json')
        response = self.client.post(MERGE_URL, {'table_nums': [1, 4]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['merge_table_cnt'], 6)
        self.assertEqual(TableGroup.objects.count(), 1)

        group = TableGroup.objects.first()
        self.assertEqual(group.representative_table.table_num, 1)

        merged_tables = Table.objects.filter(booth=self.booth, table_num__in=[1, 2, 3, 4, 5, 6])
        for table in merged_tables:
            self.assertEqual(table.group, group)

    def test_merge_tables_single_table(self):
        """단일 테이블 병합 시도 시 400"""
        self.client.force_authenticate(user=self.user)

        with suppress_request_warnings():
            response = self.client.post(MERGE_URL, {'table_nums': [1]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_merge_tables_not_found(self):
        """존재하지 않는 테이블 병합 시 404"""
        self.client.force_authenticate(user=self.user)

        with suppress_request_warnings():
            response = self.client.post(MERGE_URL, {'table_nums': [1, 9999]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_merge_tables_unauthorized(self):
        """인증 없이 병합 시 401"""
        with suppress_request_warnings():
            response = self.client.post(MERGE_URL, {'table_nums': [1, 2]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableEnterTestCase(APITestCase):
    """손님 테이블 입장 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.enter_url = f'/api/v3/django/booth/{self.booth.pk}/table/'
        self.client.cookies.clear()

    def test_enter_table_success(self):
        """테이블 입장 성공"""
        response = self.client.post(self.enter_url, {'table_num': 1}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('data', response.data)
        self.assertIn('table_usage_id', response.data['data'])
        self.assertIn('table_num', response.data['data'])
        self.assertIn('started_at', response.data['data'])

    def test_enter_table_status_changes(self):
        """입장 후 테이블 상태 IN_USE 변경 확인"""
        self.client.post(self.enter_url, {'table_num': 1}, format='json')

        table = Table.objects.get(booth=self.booth, table_num=1)
        self.assertEqual(table.status, Table.Status.IN_USE)

    def test_enter_table_usage_created(self):
        """입장 후 TableUsage 생성 확인"""
        self.client.post(self.enter_url, {'table_num': 1}, format='json')

        table = Table.objects.get(booth=self.booth, table_num=1)
        self.assertTrue(TableUsage.objects.filter(table=table, ended_at__isnull=True).exists())

    def test_enter_table_already_in_use(self):
        """이미 사용 중인 테이블 입장 시 기존 세션 반환"""
        response1 = self.client.post(self.enter_url, {'table_num': 1}, format='json')
        response2 = self.client.post(self.enter_url, {'table_num': 1}, format='json')

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response1.data['data']['table_usage_id'],
            response2.data['data']['table_usage_id']
        )

    def test_enter_table_not_found(self):
        """존재하지 않는 테이블 입장 시 404"""
        with suppress_request_warnings():
            response = self.client.post(self.enter_url, {'table_num': 9999}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_enter_table_invalid_booth(self):
        """존재하지 않는 부스 입장 시 404"""
        with suppress_request_warnings():
            response = self.client.post('/api/v3/django/booth/9999/table/', {'table_num': 1}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ─── WebSocket Tests ──────────────────────────────────────────────────────────
# JWT 미들웨어 없이 Consumer만 직접 테스트하는 앱
WS_URL = '/ws/django/booth/tables/'
WS_TEST_APP = URLRouter([
    re_path(r'^ws/django/booth/tables/$', TableConsumer.as_asgi()),
])


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableConsumerConnectTest(TransactionTestCase):
    """TableConsumer 연결/인증 테스트"""

    def setUp(self):
        client = APIClient()
        client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)

    async def test_인증없이_연결시_4001_거부(self):
        """scope에 user 없으면 4001로 연결 거부"""
        communicator = WebsocketCommunicator(WS_TEST_APP, WS_URL)
        connected, code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_booth없는_유저_연결시_4003_거부(self):
        """Booth가 없는 유저는 4003으로 연결 거부"""
        user_no_booth = await sync_to_async(User.objects.create_user)(
            username='nobooth', password='pass'
        )
        communicator = WebsocketCommunicator(WS_TEST_APP, WS_URL)
        communicator.scope['user'] = user_no_booth

        connected, code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4003)

    async def test_정상_연결시_connection_established_수신(self):
        """인증된 유저 연결 시 connection_established 메시지 수신"""
        communicator = WebsocketCommunicator(WS_TEST_APP, WS_URL)
        communicator.scope['user'] = self.user

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connection_established')
        self.assertEqual(response['booth_id'], self.booth.pk)

        await communicator.disconnect()

    async def test_클라이언트_메시지_전송시_error_응답(self):
        """클라이언트가 메시지를 보내면 error 응답 (단방향 채널)"""
        communicator = WebsocketCommunicator(WS_TEST_APP, WS_URL)
        communicator.scope['user'] = self.user

        await communicator.connect()
        await communicator.receive_json_from()  # connection_established 소비

        await communicator.send_json_to({'type': 'ping'})

        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')

        await communicator.disconnect()


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableConsumerEventTest(TransactionTestCase):
    """TableMixin 이벤트 핸들러 테스트 (group_send → 클라이언트 수신)"""

    def setUp(self):
        client = APIClient()
        client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)

    async def _connect(self):
        """연결 후 connection_established 소비까지 처리하는 헬퍼"""
        communicator = WebsocketCommunicator(WS_TEST_APP, WS_URL)
        communicator.scope['user'] = self.user
        await communicator.connect()
        await communicator.receive_json_from()  # connection_established 소비
        return communicator

    async def test_enter_table_이벤트_수신(self):
        """group_send enter_table → 클라이언트에 전달"""
        communicator = await self._connect()
        channel_layer = get_channel_layer()

        await channel_layer.group_send(
            f'booth_{self.booth.pk}.tables',
            {
                'type': 'enter_table',
                'table_num': 3,
                'started_at': '2026-02-24T10:00:00',
            }
        )

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'enter_table')
        self.assertEqual(response['data']['table_num'], 3)
        self.assertEqual(response['data']['started_at'], '2026-02-24T10:00:00')

        await communicator.disconnect()

    async def test_reset_table_이벤트_수신(self):
        """group_send reset_table → 클라이언트에 전달"""
        communicator = await self._connect()
        channel_layer = get_channel_layer()

        await channel_layer.group_send(
            f'booth_{self.booth.pk}.tables',
            {
                'type': 'reset_table',
                'table_nums': [1, 2, 3],
                'count': 3,
            }
        )

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'reset_table')
        self.assertEqual(response['data']['table_nums'], [1, 2, 3])
        self.assertEqual(response['data']['count'], 3)

        await communicator.disconnect()

    async def test_merge_table_이벤트_수신(self):
        """group_send merge_table → 클라이언트에 전달"""
        communicator = await self._connect()
        channel_layer = get_channel_layer()

        await channel_layer.group_send(
            f'booth_{self.booth.pk}.tables',
            {
                'type': 'merge_table',
                'table_nums': [1, 2, 3],
                'representative_table': 1,
                'count': 3,
            }
        )

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'merge_table')
        self.assertEqual(response['data']['representative_table'], 1)
        self.assertEqual(response['data']['count'], 3)

        await communicator.disconnect()

    async def test_다른_부스_이벤트는_수신_안됨(self):
        """다른 부스의 group_send는 수신하지 않음"""
        communicator = await self._connect()
        channel_layer = get_channel_layer()

        await channel_layer.group_send(
            'booth_99999.tables',
            {
                'type': 'enter_table',
                'table_num': 1,
                'started_at': '2026-02-24T10:00:00',
            }
        )

        self.assertTrue(await communicator.receive_nothing(timeout=1))

        await communicator.disconnect()


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableConsumerServiceIntegrationTest(TransactionTestCase):
    """Service → WebSocket 통합 테스트 (transaction.on_commit 포함)"""

    def setUp(self):
        client = APIClient()
        client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)

    def _set_tables_in_use(self, table_nums):
        """테이블 IN_USE 상태 + TableUsage 생성"""
        tables = Table.objects.filter(booth=self.booth, table_num__in=table_nums)
        tables.update(status=Table.Status.IN_USE)
        for table in tables:
            TableUsage.objects.create(table=table, started_at=now())

    async def test_테이블_입장시_enter_table_이벤트_발송(self):
        """init_or_enter_table → on_commit → enter_table 이벤트 수신"""
        communicator = WebsocketCommunicator(WS_TEST_APP, WS_URL)
        communicator.scope['user'] = self.user
        await communicator.connect()
        await communicator.receive_json_from()  # connection_established 소비

        await sync_to_async(TableService.init_or_enter_table)(self.booth, 1)

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'enter_table')
        self.assertEqual(response['data']['table_num'], 1)

        await communicator.disconnect()

    async def test_테이블_리셋시_reset_table_이벤트_발송(self):
        """reset_tables → on_commit → reset_table 이벤트 수신"""
        await sync_to_async(self._set_tables_in_use)([1, 2])

        communicator = WebsocketCommunicator(WS_TEST_APP, WS_URL)
        communicator.scope['user'] = self.user
        await communicator.connect()
        await communicator.receive_json_from()

        await sync_to_async(TableService.reset_tables)(self.booth, [1, 2])

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'reset_table')
        self.assertEqual(response['data']['count'], 2)

        await communicator.disconnect()

    async def test_테이블_병합시_merge_table_이벤트_발송(self):
        """merge_tables → on_commit → merge_table 이벤트 수신"""
        communicator = WebsocketCommunicator(WS_TEST_APP, WS_URL)
        communicator.scope['user'] = self.user
        await communicator.connect()
        await communicator.receive_json_from()

        await sync_to_async(TableService.merge_tables)(self.booth, [1, 2, 3])

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'merge_table')
        self.assertEqual(response['data']['representative_table'], 1)
        self.assertEqual(response['data']['count'], 3)

        await communicator.disconnect()