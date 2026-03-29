from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils.timezone import now
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal

from booth.models import Booth
from table.models import Table, TableGroup, TableUsage
from core.test_utils import IN_MEMORY_STORAGES, suppress_request_warnings


class BoothMyPageAPIViewTestCase(APITestCase):
    """부스 마이페이지 API 테스트"""

    def setUp(self):
        """테스트 데이터 셋업"""
        self.client = APIClient()

        # 테스트용 User 생성
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # 테스트용 Booth 생성
        self.booth = Booth.objects.create(
            user=self.user,
            name='테스트 부스',
            table_max_cnt=10,
            bank='신한은행',
            account='110-123-456789',
            depositor='홍길동',
            seat_type='PP',
            seat_fee_person=5000,
            seat_fee_table=None,
            table_limit_hours=Decimal('2.00')
        )

    def test_get_booth_data_success(self):
        """인증된 사용자의 부스 데이터 조회 성공"""
        # 로그인 (JWT 토큰 발급)
        self.client.force_authenticate(user=self.user)

        # GET 요청
        response = self.client.get('/api/v3/django/booth/mypage/')

        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], '부스 데이터를 불러왔습니다.')

        # 데이터 검증
        data = response.data['data']
        
        # 나와야하는 데이터
        expected_data = {
            'name': '테스트 부스',
            'table_max_cnt': 10,
            'bank': '신한은행',
            'account': '110-123-456789',
            'depositor': '홍길동',
            'seat_type': 'PP',
            'seat_fee_person': 5000,
            'seat_fee_table': None,
            'table_limit_hours' : "2.00"
        }

        # 검증
        for key, value in expected_data.items():
            if value is None:
                self.assertIsNone(data[key])
            else:
                self.assertEqual(data[key], value)

    def test_get_booth_data_unauthorized(self):
        """인증 없이 부스 데이터 조회 시 실패"""
        # 인증 없이 요청
        response = self.client.get('/api/v3/django/booth/mypage/')

        # 401 Unauthorized 응답
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_booth_data_success(self):
        self.client.force_authenticate(user=self.user)
        
        patch_data = {
            "name": "신규 부스update",
            "table_max_cnt": 101,
            "account": "1234567890update",
            "depositor": "홍길동update",
            "bank": "신한은행update",
            "seat_type": "PT",
            "seat_fee_person": 1,
            "seat_fee_table": 30001,
            "table_limit_hours": "3.00"
        }

        response = self.client.patch(
            '/api/v3/django/booth/mypage/',
            data=patch_data,
            format='json'
        )

        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], '업데이트가 완료되었습니다.')
        
        data = response.data['data']        

        expected_data = {
            "name": "신규 부스update",
            "account": "1234567890update",
            "depositor": "홍길동update",
            "bank": "신한은행update",
            "seat_type": "PT",
            "seat_fee_person": 1,
            "seat_fee_table": 30001,
            "table_limit_hours": "3.00"
        }

        # 검증
        for key, value in expected_data.items():
            if value is None:
                self.assertIsNone(data[key])
            else:
                self.assertEqual(data[key], value)

    def test_patch_booth_data_fail_vaildate(self):
        """유효성 검사 실패시 400 반환"""
        self.client.force_authenticate(user=self.user)

        patch_data = {
            "name": "신규 부스",
            "account": "1234567890",
            "depositor": "홍길동",
            "bank": "신한은행",
            "seat_type": "PT",
            "seat_fee_person": "string",
            "seat_fee_table": "string",
            "table_limit_hours": "2.00"
        }

        response = self.client.patch(
            '/api/v3/django/booth/mypage/',
            data=patch_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)





SIGNUP_URL = '/api/v3/django/auth/signup/'
RESET_TABLE_USAGE_URL  = '/api/v3/django/booth/mypage/reset-table-data/'
MERGE_URL  = '/api/v3/django/booth/tables/merge/'

VALID_SIGNUP_DATA = {
    "username": "testuser",
    "password": "testpass123",
    "booth_data": {
        "name": "테스트 부스",
        "table_max_cnt": 5,
        "account": "1234567890",
        "depositor": "홍길동",
        "bank": "신한은행",
        "seat_type": "NO",
        "seat_fee_person": 0,
        "seat_fee_table": 0,
        "table_limit_hours": 2.0,
    }
}


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class BoothTableUsagePurgeTestCase(APITestCase):
    """TableUsage 전체 삭제 API 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.client.post(SIGNUP_URL, VALID_SIGNUP_DATA, format='json')
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.client.cookies.clear()

    def _set_in_use(self, table_num):
        """테이블 IN_USE + 활성 TableUsage 생성"""
        table = Table.objects.get(booth=self.booth, table_num=table_num)
        table.status = Table.Status.IN_USE
        table.save()
        return TableUsage.objects.create(table=table, started_at=now())

    def _create_ended_usage(self, table_num):
        """종료된 TableUsage 생성 (테이블 상태는 AVAILABLE 유지)"""
        table = Table.objects.get(booth=self.booth, table_num=table_num)
        return TableUsage.objects.create(table=table, started_at=now(), ended_at=now())

    def test_purge_success(self):
        """모든 테이블 AVAILABLE 상태에서 삭제 성공 - 200"""
        self.client.force_authenticate(user=self.user)
        self._create_ended_usage(1)

        response = self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('deleted_count', response.data['data'])

    def test_purge_deletes_all_usages(self):
        """삭제 후 부스의 TableUsage가 0개"""
        self.client.force_authenticate(user=self.user)
        self._create_ended_usage(1)
        self._create_ended_usage(2)
        self._create_ended_usage(2)  # 같은 테이블에 여러 기록
        self.assertEqual(TableUsage.objects.filter(table__booth=self.booth).count(), 3)

        self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(TableUsage.objects.filter(table__booth=self.booth).count(), 0)

    def test_purge_returns_deleted_count(self):
        """응답에 삭제된 개수 반환"""
        self.client.force_authenticate(user=self.user)
        self._create_ended_usage(1)
        self._create_ended_usage(2)

        response = self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(response.data['data']['deleted_count'], 2)

    def test_purge_blocked_when_any_table_in_use(self):
        """IN_USE 테이블이 있으면 400"""
        self.client.force_authenticate(user=self.user)
        self._set_in_use(1)

        with suppress_request_warnings():
            response = self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_purge_blocked_when_one_of_many_is_in_use(self):
        """여러 테이블 중 한 개만 IN_USE여도 400"""
        self.client.force_authenticate(user=self.user)
        self._create_ended_usage(1)  # 종료된 기록
        self._set_in_use(2)          # 사용 중

        with suppress_request_warnings():
            response = self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_purge_does_not_delete_when_blocked(self):
        """400 응답 시 기존 TableUsage는 삭제되지 않음"""
        self.client.force_authenticate(user=self.user)
        self._create_ended_usage(1)
        self._set_in_use(2)
        count_before = TableUsage.objects.filter(table__booth=self.booth).count()

        with suppress_request_warnings():
            self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(TableUsage.objects.filter(table__booth=self.booth).count(), count_before)

    def test_purge_no_usages_returns_200(self):
        """TableUsage가 없어도 200 (deleted_count=0)"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['deleted_count'], 0)

    def test_purge_also_deletes_groups(self):
        """그룹도 함께 해제 및 삭제"""
        self.client.force_authenticate(user=self.user)
        self.client.post(MERGE_URL, {'table_nums': [1, 2]}, format='json')
        self.assertEqual(TableGroup.objects.count(), 1)

        self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(TableGroup.objects.count(), 0)
        # 테이블의 group FK도 NULL로 초기화됨
        for table in Table.objects.filter(booth=self.booth):
            self.assertIsNone(table.group)

    def test_purge_unauthorized(self):
        """미인증 시 401"""
        with suppress_request_warnings():
            response = self.client.delete(RESET_TABLE_USAGE_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class BoothAuthenticationIntegrationTestCase(APITestCase):
    """Authentication API를 사용한 통합 테스트 (선택사항)"""

    def test_signup_and_get_booth(self):
        """회원가입 후 부스 데이터 조회"""
        # 1. 회원가입 (Authentication API 사용)
        signup_data = {
            "username": "newuser",
            "password": "testpass123",
            "booth_data": {
                "name": "신규 부스",
                "table_max_cnt": 10,
                "account": "1234567890",
                "depositor": "홍길동",
                "bank": "신한은행",
                "seat_type": "PT",
                "seat_fee_person": 0,
                "seat_fee_table": 30000,
                "table_limit_hours": 2.0
            }
        }

        signup_response = self.client.post(
            '/api/v3/django/auth/signup/',
            data=signup_data,
            format='json'
        )

        self.assertEqual(signup_response.status_code, status.HTTP_201_CREATED)

        # 2. 생성된 User로 인증
        user = User.objects.get(username='newuser')
        self.client.force_authenticate(user=user)

        # 3. 부스 데이터 조회
        response = self.client.get('/api/v3/django/booth/mypage/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 회원가입 시 입력한 데이터와 일치하는지 확인
        data = response.data['data']

        # 나와야하는 데이터
        expected_data = {
            "name": "신규 부스",
            "table_max_cnt": 10,
            "account": "1234567890",
            "depositor": "홍길동",
            "bank": "신한은행",
            "seat_type": "PT",
            "seat_fee_person": 0,
            "seat_fee_table": 30000,
            "table_limit_hours": "2.00"
        }

        # 검증
        for key, value in expected_data.items():
            if value is None:
                self.assertIsNone(data[key])
            else:
                self.assertEqual(data[key], value)
