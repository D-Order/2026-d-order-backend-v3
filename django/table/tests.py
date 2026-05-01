import logging
import threading
from datetime import timedelta
from django.test import override_settings, TransactionTestCase, TestCase
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
from menu.models import Menu
from order.models import Order, OrderItem
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
        self.assertIsInstance(response.data['data'], list)
        self.assertEqual(len(response.data['data']), VALID_SIGNUP_DATA['booth_data']['table_max_cnt'])

    def test_get_tables_fields(self):
        """응답 필드 구조 검증"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TABLE_LIST_URL)

        for table_data in response.data['data']:
            self.assertIn('table_num', table_data)
            self.assertIn('status', table_data)
            self.assertIn('group', table_data)
            self.assertIn('accumulated_amount', table_data)
            self.assertIn('order_list', table_data)
            self.assertIn('started_at', table_data)

    def test_get_tables_initial_state(self):
        """초기 상태: 전부 AVAILABLE, group None, started_at None"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TABLE_LIST_URL)

        for table_data in response.data['data']:
            self.assertEqual(table_data['status'], 'AVAILABLE')
            self.assertIsNone(table_data['group'])
            self.assertIsNone(table_data['started_at'])

    def test_get_tables_ordered_by_table_num(self):
        """table_num 오름차순 정렬 검증"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TABLE_LIST_URL)

        table_nums = [t['table_num'] for t in response.data['data']]
        self.assertEqual(table_nums, sorted(table_nums))

    def test_get_tables_order_list_empty_when_no_orders(self):
        """주문 없는 테이블의 order_list는 빈 리스트"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TABLE_LIST_URL)

        for table_data in response.data['data']:
            self.assertEqual(table_data['order_list'], [])

    def test_get_tables_order_list_flat_with_name_quantity(self):
        """order_list가 name, quantity만 가진 flat list로 반환"""
        self.client.force_authenticate(user=self.user)

        table = Table.objects.get(booth=self.booth, table_num=1)
        table.status = Table.Status.IN_USE
        table.save()
        usage = TableUsage.objects.create(table=table, started_at=now())
        menu = Menu.objects.create(booth=self.booth, name='아메리카노', price=4000, stock=10)
        order = Order.objects.create(
            table_usage=usage, order_price=8000, original_price=8000, order_status='PAID',
        )
        OrderItem.objects.create(
            order=order, menu=menu, quantity=2, fixed_price=4000, status='COOKING',
        )

        response = self.client.get(TABLE_LIST_URL)
        table_data = next(t for t in response.data['data'] if t['table_num'] == 1)
        order_list = table_data['order_list']

        self.assertEqual(len(order_list), 1)
        self.assertEqual(order_list[0]['name'], '아메리카노')
        self.assertEqual(order_list[0]['quantity'], 2)
        self.assertNotIn('fixed_price', order_list[0])

    def test_get_tables_order_list_newest_first(self):
        """order_list는 최신 항목이 먼저 반환"""
        self.client.force_authenticate(user=self.user)

        table = Table.objects.get(booth=self.booth, table_num=1)
        table.status = Table.Status.IN_USE
        table.save()
        usage = TableUsage.objects.create(table=table, started_at=now())
        order = Order.objects.create(
            table_usage=usage, order_price=10000, original_price=10000, order_status='PAID',
        )
        menu1 = Menu.objects.create(booth=self.booth, name='첫번째메뉴', price=3000, stock=10)
        menu2 = Menu.objects.create(booth=self.booth, name='두번째메뉴', price=3000, stock=10)
        OrderItem.objects.create(order=order, menu=menu1, quantity=1, fixed_price=3000, status='COOKING')
        OrderItem.objects.create(order=order, menu=menu2, quantity=1, fixed_price=3000, status='COOKING')

        response = self.client.get(TABLE_LIST_URL)
        table_data = next(t for t in response.data['data'] if t['table_num'] == 1)
        order_list = table_data['order_list']

        self.assertEqual(order_list[0]['name'], '두번째메뉴')
        self.assertEqual(order_list[1]['name'], '첫번째메뉴')

    def test_get_tables_order_list_max_3(self):
        """order_list는 최대 3개 반환"""
        self.client.force_authenticate(user=self.user)

        table = Table.objects.get(booth=self.booth, table_num=1)
        table.status = Table.Status.IN_USE
        table.save()
        usage = TableUsage.objects.create(table=table, started_at=now())
        order = Order.objects.create(
            table_usage=usage, order_price=20000, original_price=20000, order_status='PAID',
        )
        for i in range(5):
            menu = Menu.objects.create(booth=self.booth, name=f'메뉴{i}', price=4000, stock=10)
            OrderItem.objects.create(
                order=order, menu=menu, quantity=1, fixed_price=4000, status='COOKING',
            )

        response = self.client.get(TABLE_LIST_URL)
        table_data = next(t for t in response.data['data'] if t['table_num'] == 1)

        self.assertLessEqual(len(table_data['order_list']), 3)

    def test_get_tables_unauthorized(self):
        """인증 없이 조회 시 401"""
        response = self.client.get(TABLE_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableRetrieveTestCase(APITestCase):
    """테이블 디테일 조회 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.client.cookies.clear()

    def _detail_url(self, table_num):
        return f'{TABLE_LIST_URL}{table_num}/'

    def _activate_table(self, table_num):
        """테이블 IN_USE + TableUsage 생성"""
        table = Table.objects.get(booth=self.booth, table_num=table_num)
        table.status = Table.Status.IN_USE
        table.save()
        return TableUsage.objects.create(table=table, started_at=now())

    def _create_order(self, usage, menu_name='아메리카노', price=4000, quantity=2):
        """Order + OrderItem 생성"""
        menu = Menu.objects.create(booth=self.booth, name=menu_name, price=price, stock=10)
        order = Order.objects.create(
            table_usage=usage,
            order_price=price * quantity,
            original_price=price * quantity,
            order_status='PAID',
        )
        OrderItem.objects.create(
            order=order, menu=menu, quantity=quantity,
            fixed_price=price, status='COOKING',
        )
        return order

    def test_retrieve_success(self):
        """디테일 조회 성공 - 200"""
        self.client.force_authenticate(user=self.user)
        usage = self._activate_table(1)
        self._create_order(usage)

        response = self.client.get(self._detail_url(1))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_retrieve_response_fields(self):
        """응답 필드 구조 검증 - table_number, table_total_price, order_list"""
        self.client.force_authenticate(user=self.user)
        usage = self._activate_table(1)
        self._create_order(usage)

        response = self.client.get(self._detail_url(1))
        data = response.data['data']

        self.assertIn('table_number', data)
        self.assertIn('table_total_price', data)
        self.assertIn('order_list', data)

    def test_retrieve_order_list_grouped(self):
        """여러 Order가 order_list로 주문별 그룹핑되어 반환"""
        self.client.force_authenticate(user=self.user)
        usage = self._activate_table(1)
        self._create_order(usage, menu_name='아메리카노', price=4000, quantity=1)
        self._create_order(usage, menu_name='라떼', price=5000, quantity=2)

        response = self.client.get(self._detail_url(1))
        order_list = response.data['data']['order_list']

        self.assertIsInstance(order_list, list)
        self.assertEqual(len(order_list), 2)

    def test_retrieve_order_item_fields(self):
        """order_list 각 주문의 order_items에 id, name, quantity, fixed_price 포함"""
        self.client.force_authenticate(user=self.user)
        usage = self._activate_table(1)
        self._create_order(usage, menu_name='아메리카노', price=4000, quantity=2)

        response = self.client.get(self._detail_url(1))
        order = response.data['data']['order_list'][0]
        item = order['order_items'][0]

        self.assertIn('id', item)
        self.assertIsNotNone(item['id'])
        self.assertEqual(item['name'], '아메리카노')
        self.assertEqual(item['quantity'], 2)
        self.assertEqual(item['fixed_price'], 4000)
        self.assertIn('order_number', order)
        self.assertIn('created_at', order)

    def test_retrieve_total_price(self):
        """table_total_price가 usage.accumulated_amount와 일치"""
        self.client.force_authenticate(user=self.user)
        usage = self._activate_table(1)
        self._create_order(usage, price=4000, quantity=2)   # 8000
        self._create_order(usage, menu_name='라떼', price=5000, quantity=1)  # 5000
        usage.accumulated_amount = 13000
        usage.save()

        response = self.client.get(self._detail_url(1))

        self.assertEqual(response.data['data']['table_total_price'], 13000)

    def test_retrieve_order_list_order_number(self):
        """order_list는 주문 순서대로 order_number 부여"""
        self.client.force_authenticate(user=self.user)
        usage = self._activate_table(1)
        self._create_order(usage, menu_name='첫번째메뉴', price=3000, quantity=1)
        self._create_order(usage, menu_name='두번째메뉴', price=3000, quantity=1)

        response = self.client.get(self._detail_url(1))
        order_list = response.data['data']['order_list']

        self.assertEqual(order_list[0]['order_number'], 1)
        self.assertEqual(order_list[1]['order_number'], 2)

    def test_retrieve_no_active_usage_returns_404(self):
        """활성 세션 없는 테이블 조회 시 404"""
        self.client.force_authenticate(user=self.user)

        with suppress_request_warnings():
            response = self.client.get(self._detail_url(1))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_table_not_found_returns_404(self):
        """존재하지 않는 테이블 조회 시 404"""
        self.client.force_authenticate(user=self.user)

        with suppress_request_warnings():
            response = self.client.get(self._detail_url(9999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_unauthorized_returns_401(self):
        """인증 없이 조회 시 401"""
        with suppress_request_warnings():
            response = self.client.get(self._detail_url(1))

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

    def test_reset_merged_tables_without_active_session(self):
        """병합되었지만 IN_USE가 아닌 테이블도 초기화로 병합 해제 가능 (#307)"""
        self.client.force_authenticate(user=self.user)
        self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')

        for table_num in [1, 2, 3]:
            table = Table.objects.get(booth=self.booth, table_num=table_num)
            self.assertEqual(table.status, Table.Status.ACTIVE)
            self.assertIsNotNone(table.group)

        response = self.client.post(RESET_URL, {'table_nums': [1]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for table_num in [1, 2, 3]:
            table = Table.objects.get(booth=self.booth, table_num=table_num)
            self.assertEqual(table.status, Table.Status.ACTIVE)
            self.assertIsNone(table.group)

    def test_reset_idle_unmerged_table_rejected(self):
        """병합되지 않은 미사용 테이블은 여전히 초기화 거부"""
        self.client.force_authenticate(user=self.user)

        with suppress_request_warnings():
            response = self.client.post(RESET_URL, {'table_nums': [1]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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

    def test_병합_후_모든_테이블_IN_USE(self):
        """세션 있는 테이블 병합 후 모든 테이블이 IN_USE여야 함"""
        from table.models import TableUsage
        self.client.force_authenticate(user=self.user)
        t1 = Table.objects.get(booth=self.booth, table_num=1)
        t2 = Table.objects.get(booth=self.booth, table_num=2)
        t3 = Table.objects.get(booth=self.booth, table_num=3)

        # t2, t3만 IN_USE (t1은 ACTIVE)
        TableUsage.objects.create(table=t2, started_at=now())
        TableUsage.objects.create(table=t3, started_at=now())
        t2.status = Table.Status.IN_USE
        t2.save()
        t3.status = Table.Status.IN_USE
        t3.save()

        self.client.post(MERGE_URL, {'table_nums': [1, 2, 3]}, format='json')

        for table in Table.objects.filter(booth=self.booth, table_num__in=[1, 2, 3]):
            self.assertEqual(table.status, Table.Status.IN_USE)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableEnterTestCase(APITestCase):
    """손님 테이블 입장 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.enter_url = f'/api/v3/django/booth/{self.booth.public_id}/table/'
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
            response = self.client.post('/api/v3/django/booth/00000000-0000-0000-0000-000000000000/table/', {'table_num': 1}, format='json')

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
        self.assertEqual(response['data']['booth_id'], self.booth.pk)
        self.assertIn('timestamp', response)

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
                'data': {
                    'table_num': 3,
                    'started_at': '2026-02-24T10:00:00',
                }
            }
        )

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'enter_table')
        self.assertIn('timestamp', response)
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
                'data': {
                    'table_nums': [1, 2, 3],
                    'count': 3,
                }
            }
        )

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'reset_table')
        self.assertIn('timestamp', response)
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
                'data': {
                    'table_nums': [1, 2, 3],
                    'representative_table': 1,
                    'count': 3,
                }
            }
        )

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['type'], 'merge_table')
        self.assertIn('timestamp', response)
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
                'data': {
                    'table_num': 1,
                    'started_at': '2026-02-24T10:00:00',
                }
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


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class MergeActiveUsagesTestCase(TestCase):
    """TableService._merge_active_usages 단위 테스트

    Known limitation:
        rep_cart가 other_carts에서 pop된 경우, 해당 cart의 pending 쿠폰이
        나머지 other_carts의 historical 쿠폰 이전으로 인해 round가 밀려
        유실될 수 있음. (rep_cart.round > pending 쿠폰의 round)
    """

    def setUp(self):
        client = APIClient()
        client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.t1 = Table.objects.get(booth=self.booth, table_num=1)
        self.t2 = Table.objects.get(booth=self.booth, table_num=2)
        self.t3 = Table.objects.get(booth=self.booth, table_num=3)
        self.menu1 = Menu.objects.create(booth=self.booth, name='아메리카노', price=4000, stock=10)
        self.menu2 = Menu.objects.create(booth=self.booth, name='라떼', price=5000, stock=10)

        from coupon.models import Coupon
        self.coupon = Coupon.objects.create(
            booth=self.booth, name='10% 할인', discount_type='RATE', discount_value=10
        )
        self._code_counter = 0

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _usage(self, table, minutes_ago=0, accumulated=0):
        return TableUsage.objects.create(
            table=table,
            started_at=now() - timedelta(minutes=minutes_ago),
            accumulated_amount=accumulated,
        )

    def _cart(self, usage, cart_price=0, round=0):
        from cart.models import Cart
        return Cart.objects.create(table_usage=usage, cart_price=cart_price, round=round)

    def _cart_item(self, cart, menu, quantity=1):
        from cart.models import CartItem
        return CartItem.objects.create(cart=cart, menu=menu, quantity=quantity, price_at_cart=menu.price)

    def _coupon_code(self):
        self._code_counter += 1
        from coupon.models import CouponCode
        return CouponCode.objects.create(coupon=self.coupon, code=f'CODE{self._code_counter:04d}')

    def _cart_coupon_apply(self, cart, round, code):
        from coupon.models import CartCouponApply
        return CartCouponApply.objects.create(cart=cart, round=round, coupon_code=code)

    def _table_coupon(self, usage):
        from coupon.models import TableCoupon
        return TableCoupon.objects.create(coupon=self.coupon, table_usage=usage)

    def _order(self, usage, price=1000):
        return Order.objects.create(table_usage=usage, order_price=price, original_price=price, order_status='PAID')

    def _call(self, tables):
        all_table_ids = [t.id for t in tables]
        representative_table = min(tables, key=lambda t: t.table_num)
        TableService._merge_active_usages(all_table_ids, representative_table)
        return representative_table

    def _rep_usage(self, rep_table):
        return TableUsage.objects.get(table=rep_table, ended_at__isnull=True)

    # ─── 기본 동작 ────────────────────────────────────────────────────────

    def test_활성_usage_없으면_아무것도_변경되지_않음(self):
        self._call([self.t1, self.t2])
        self.assertEqual(TableUsage.objects.count(), 0)

    def test_rep_테이블에만_usage_있으면_종료되지_않음(self):
        usage = self._usage(self.t1, minutes_ago=30, accumulated=5000)
        self._call([self.t1, self.t2])
        usage.refresh_from_db()
        self.assertIsNone(usage.ended_at)
        self.assertEqual(usage.table, self.t1)

    # ─── TableUsage 병합 ──────────────────────────────────────────────────

    def test_accumulated_amount_합산됨(self):
        self._usage(self.t1, accumulated=3000)
        self._usage(self.t2, accumulated=5000)
        self._call([self.t1, self.t2])
        self.assertEqual(self._rep_usage(self.t1).accumulated_amount, 8000)

    def test_accumulated_amount_3개_합산됨(self):
        self._usage(self.t1, accumulated=1000)
        self._usage(self.t2, accumulated=2000)
        self._usage(self.t3, accumulated=3000)
        self._call([self.t1, self.t2, self.t3])
        self.assertEqual(self._rep_usage(self.t1).accumulated_amount, 6000)

    def test_earliest_started_at_적용됨(self):
        early = now() - timedelta(minutes=60)
        late = now() - timedelta(minutes=10)
        TableUsage.objects.create(table=self.t1, started_at=late)
        TableUsage.objects.create(table=self.t2, started_at=early)
        self._call([self.t1, self.t2])
        rep = self._rep_usage(self.t1)
        self.assertAlmostEqual(rep.started_at.timestamp(), early.timestamp(), delta=1)

    def test_other_usage_삭제됨(self):
        self._usage(self.t1)
        self._usage(self.t2)
        self._usage(self.t3)
        self._call([self.t1, self.t2, self.t3])
        self.assertEqual(TableUsage.objects.filter(ended_at__isnull=True).count(), 1)
        self.assertTrue(TableUsage.objects.filter(table=self.t1, ended_at__isnull=True).exists())

    def test_rep_테이블_usage_없을때_가장_이른_usage_재할당됨(self):
        TableUsage.objects.create(table=self.t2, started_at=now() - timedelta(minutes=60))
        TableUsage.objects.create(table=self.t3, started_at=now() - timedelta(minutes=10))
        self._call([self.t1, self.t2, self.t3])
        self.assertTrue(TableUsage.objects.filter(table=self.t1, ended_at__isnull=True).exists())
        self.assertEqual(TableUsage.objects.filter(ended_at__isnull=True).count(), 1)

    # ─── Order 재할당 ─────────────────────────────────────────────────────

    def test_other_usage의_order가_rep_usage로_재할당됨(self):
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        o1 = self._order(u1)
        o2 = self._order(u2)
        self._call([self.t1, self.t2])
        rep = self._rep_usage(self.t1)
        o1.refresh_from_db()
        o2.refresh_from_db()
        self.assertEqual(o1.table_usage, rep)
        self.assertEqual(o2.table_usage, rep)

    def test_order_개수_손실_없음(self):
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        for _ in range(3):
            self._order(u1)
        for _ in range(2):
            self._order(u2)
        self._call([self.t1, self.t2])
        rep = self._rep_usage(self.t1)
        self.assertEqual(Order.objects.filter(table_usage=rep).count(), 5)

    # ─── Cart 병합 ────────────────────────────────────────────────────────

    def test_rep_cart_없을때_other_cart_재할당됨(self):
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        cart2 = self._cart(u2, cart_price=5000)
        self._call([self.t1, self.t2])
        cart2.refresh_from_db()
        self.assertEqual(cart2.table_usage, self._rep_usage(self.t1))

    def test_cart_items_중복_없을때_rep_cart로_이전됨(self):
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        cart1 = self._cart(u1)
        cart2 = self._cart(u2)
        self._cart_item(cart1, self.menu1, quantity=1)
        self._cart_item(cart2, self.menu2, quantity=2)
        self._call([self.t1, self.t2])
        self.assertEqual(cart1.items.count(), 2)

    def test_cart_items_동일_메뉴_수량_합산됨(self):
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        cart1 = self._cart(u1)
        cart2 = self._cart(u2)
        self._cart_item(cart1, self.menu1, quantity=1)
        self._cart_item(cart2, self.menu1, quantity=3)
        self._call([self.t1, self.t2])
        item = cart1.items.get(menu=self.menu1)
        self.assertEqual(item.quantity, 4)
        self.assertEqual(cart1.items.count(), 1)

    def test_cart_price_합산됨(self):
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        cart1 = self._cart(u1, cart_price=3000)
        cart2 = self._cart(u2, cart_price=7000)
        self._call([self.t1, self.t2])
        cart1.refresh_from_db()
        self.assertEqual(cart1.cart_price, 10000)

    def test_other_cart_삭제됨(self):
        from cart.models import Cart
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        self._cart(u1)
        self._cart(u2)
        self._call([self.t1, self.t2])
        self.assertEqual(Cart.objects.count(), 1)

    def test_cart_item_개수_손실_없음(self):
        from cart.models import CartItem
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        cart1 = self._cart(u1)
        cart2 = self._cart(u2)
        self._cart_item(cart1, self.menu1, quantity=1)
        self._cart_item(cart2, self.menu2, quantity=2)  # 다른 메뉴 → 이전
        self._call([self.t1, self.t2])
        self.assertEqual(CartItem.objects.filter(cart=cart1).count(), 2)

    # ─── CartCouponApply ──────────────────────────────────────────────────

    def test_과거_라운드_쿠폰_rep_cart로_이전됨(self):
        from coupon.models import CartCouponApply
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        cart1 = self._cart(u1, round=0)
        cart2 = self._cart(u2, round=2)  # round 0, 1은 과거
        self._cart_coupon_apply(cart2, round=0, code=self._coupon_code())
        self._cart_coupon_apply(cart2, round=1, code=self._coupon_code())
        self._call([self.t1, self.t2])
        self.assertEqual(CartCouponApply.objects.filter(cart=cart1).count(), 2)

    def test_과거_라운드_쿠폰_이전_후_other_cart_레코드_없음(self):
        from coupon.models import CartCouponApply
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        self._cart(u1, round=0)
        cart2 = self._cart(u2, round=2)
        code_a = self._coupon_code()
        self._cart_coupon_apply(cart2, round=0, code=code_a)
        self._call([self.t1, self.t2])
        # cart2는 삭제됐으므로 code_a의 CartCouponApply는 cart1로 이전
        self.assertEqual(CartCouponApply.objects.filter(coupon_code=code_a).count(), 1)
        self.assertEqual(CartCouponApply.objects.get(coupon_code=code_a).cart.table_usage.table, self.t1)

    def test_pending_쿠폰_CartCouponApply_삭제됨(self):
        from coupon.models import CartCouponApply
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        self._cart(u1, round=0)
        cart2 = self._cart(u2, round=1)  # round 1이 현재 (pending)
        code_past = self._coupon_code()
        code_pending = self._coupon_code()
        self._cart_coupon_apply(cart2, round=0, code=code_past)     # 과거
        self._cart_coupon_apply(cart2, round=1, code=code_pending)  # pending
        self._call([self.t1, self.t2])
        self.assertFalse(CartCouponApply.objects.filter(coupon_code=code_pending).exists())

    def test_pending_쿠폰_code_used_at_None_유지됨(self):
        """삭제된 pending 쿠폰의 CouponCode.used_at은 None → 재사용 가능"""
        from coupon.models import CartCouponApply
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        self._cart(u1)
        cart2 = self._cart(u2, round=0)
        code = self._coupon_code()
        self._cart_coupon_apply(cart2, round=0, code=code)
        self._call([self.t1, self.t2])
        code.refresh_from_db()
        self.assertIsNone(code.used_at)

    def test_rep_cart_round_마이그레이션_후_충돌_없음(self):
        """이전된 쿠폰의 round가 rep_cart.round를 초과하면 rep_cart.round가 업데이트됨"""
        from coupon.models import CartCouponApply
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        cart1 = self._cart(u1, round=0)
        cart2 = self._cart(u2, round=2)  # historical: round 0, 1
        self._cart_coupon_apply(cart2, round=0, code=self._coupon_code())
        self._cart_coupon_apply(cart2, round=1, code=self._coupon_code())
        self._call([self.t1, self.t2])
        cart1.refresh_from_db()
        # round_offset = 0 (rep_cart.round) + 2 historical = 2
        self.assertEqual(cart1.round, 2)
        # 다음 주문 round += 1 → 3, round 3에 CartCouponApply 없음
        self.assertFalse(CartCouponApply.objects.filter(cart=cart1, round=3).exists())

    def test_rep_cart_pending_쿠폰_유지됨(self):
        """rep_cart의 pending 쿠폰은 other_cart 이전에 의해 영향받지 않음"""
        from coupon.models import CartCouponApply
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        cart1 = self._cart(u1, round=0)
        cart2 = self._cart(u2, round=0)  # other cart, 쿠폰 없음
        code_rep = self._coupon_code()
        self._cart_coupon_apply(cart1, round=0, code=code_rep)  # rep_cart pending
        self._call([self.t1, self.t2])
        # rep_cart의 pending 쿠폰이 살아있음
        self.assertTrue(CartCouponApply.objects.filter(cart=cart1, coupon_code=code_rep).exists())

    # ─── TableCoupon ──────────────────────────────────────────────────────

    def test_rep_usage_쿠폰_없을때_other에서_재할당됨(self):
        from coupon.models import TableCoupon
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        self._table_coupon(u2)
        self._call([self.t1, self.t2])
        self.assertTrue(TableCoupon.objects.filter(table_usage=self._rep_usage(self.t1)).exists())
        self.assertEqual(TableCoupon.objects.count(), 1)

    def test_rep_usage_쿠폰_있을때_other_쿠폰_삭제됨(self):
        from coupon.models import TableCoupon, Coupon
        coupon2 = Coupon.objects.create(
            booth=self.booth, name='5000원 할인', discount_type='AMOUNT', discount_value=5000
        )
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        self._table_coupon(u1)
        TableCoupon.objects.create(coupon=coupon2, table_usage=u2)
        self._call([self.t1, self.t2])
        self.assertEqual(TableCoupon.objects.count(), 1)
        self.assertTrue(TableCoupon.objects.filter(table_usage=self._rep_usage(self.t1)).exists())

    def test_여러_other_쿠폰_중_하나만_rep_usage로_재할당됨(self):
        from coupon.models import TableCoupon, Coupon
        coupon2 = Coupon.objects.create(
            booth=self.booth, name='2000원 할인', discount_type='AMOUNT', discount_value=2000
        )
        u1 = self._usage(self.t1)
        u2 = self._usage(self.t2)
        u3 = self._usage(self.t3)
        TableCoupon.objects.create(coupon=self.coupon, table_usage=u2)
        TableCoupon.objects.create(coupon=coupon2, table_usage=u3)
        self._call([self.t1, self.t2, self.t3])
        self.assertEqual(TableCoupon.objects.count(), 1)
        self.assertTrue(TableCoupon.objects.filter(table_usage=self._rep_usage(self.t1)).exists())

    # ─── 회귀 테스트 ──────────────────────────────────────────────────────

    def test_paid_order_있는_테이블_병합시_ProtectedError_없음(self):
        """PAID 주문이 있는 테이블 병합 시 ProtectedError 없이 성공해야 함"""
        from cart.models import Cart
        self._usage(self.t1, minutes_ago=30)
        usage2 = self._usage(self.t2, minutes_ago=20)
        other_cart = Cart.objects.create(table_usage=usage2, cart_price=5000)
        order = Order.objects.create(
            table_usage=usage2,
            cart=other_cart,
            order_price=5000,
            original_price=5000,
            order_status='PAID',
        )

        self._call([self.t1, self.t2])

        order.refresh_from_db()
        rep_cart = Cart.objects.get(table_usage=self._rep_usage(self.t1))
        self.assertEqual(order.cart, rep_cart)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class TableConcurrentEnterTestCase(TransactionTestCase):
    """테이블 입장 동시 호출 시 TableUsage 중복 생성 방지 테스트"""

    def setUp(self):
        client = APIClient()
        client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)

    def test_동시_입장_2개_요청시_TableUsage_하나만_생성(self):
        """동시에 같은 테이블에 2개 입장 요청이 들어와도 TableUsage가 1개만 생성되어야 한다"""
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def enter():
            try:
                barrier.wait()
                usage = TableService.init_or_enter_table(self.booth, 1)
                results.append(usage.id)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=enter)
        t2 = threading.Thread(target=enter)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(errors), 0, f"예외 발생: {errors}")
        active_usages = TableUsage.objects.filter(
            table__booth=self.booth,
            table__table_num=1,
            ended_at__isnull=True,
        )
        self.assertEqual(active_usages.count(), 1, "TableUsage가 1개여야 합니다")
        self.assertEqual(results[0], results[1], "두 요청이 같은 TableUsage를 반환해야 합니다")

    def test_동시_입장_5개_요청시_TableUsage_하나만_생성(self):
        """5개 동시 요청에도 TableUsage가 1개만 생성되어야 한다"""
        results = []
        errors = []
        n = 5
        barrier = threading.Barrier(n)

        def enter():
            try:
                barrier.wait()
                usage = TableService.init_or_enter_table(self.booth, 2)
                results.append(usage.id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=enter) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"예외 발생: {errors}")
        active_usages = TableUsage.objects.filter(
            table__booth=self.booth,
            table__table_num=2,
            ended_at__isnull=True,
        )
        self.assertEqual(active_usages.count(), 1, "TableUsage가 1개여야 합니다")
        self.assertEqual(len(set(results)), 1, "모든 요청이 같은 TableUsage를 반환해야 합니다")