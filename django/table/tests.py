import logging
from tokenize import group
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from booth.models import Booth
from table.models import Table, TableGroup, TableUsage

User = get_user_model()
logger = logging.getLogger(__name__)

class TableManagementViewSetTestCase(APITestCase):
    """테이블 관리 API 테스트 케이스"""

    def setUp(self):
        """테스트 데이터 초기화"""
        self.client = APIClient()
        self.signup_url = '/api/v3/django/auth/signup/'

        self.valid_data = {
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

        # 회원가입
        signup_response = self.client.post(
            self.signup_url,
            self.valid_data,
            format='json'
        )
        # User, Booth 조회
        self.user = User.objects.get(username='testuser')
        self.booth = Booth.objects.get(user=self.user)
        self.client.cookies.clear()  # 인증 정보 제거


    def test_get_tables(self):
        """테이블 목록 조회 테스트"""
        # 인증
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/v3/django/booth/tables/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

        expected_count = self.valid_data['booth_data']['table_max_cnt']
        self.assertEqual(len(response.data), expected_count)

        # 각 테이블 데이터 검증
        for table_data in response.data:
            self.assertIn('booth', table_data)
            self.assertIn('table_num', table_data)
            self.assertIn('status', table_data)
            self.assertIn('group', table_data)
            self.assertIn('total_revenue', table_data)
            self.assertIn('recent_3_orders', table_data)
            self.assertIn('started_at', table_data)

            self.assertIsInstance(table_data['booth'], int)
            self.assertIsInstance(table_data['table_num'], int)
            self.assertEqual(table_data['booth'], self.booth.pk)

            # 회원가입 직후니 다 AVAILABLE + Group None이여야함
            self.assertEqual(table_data['status'], 'AVAILABLE')
            self.assertIsNone(table_data['group'])
            self.assertIsNone(table_data['started_at'])

    def test_get_tables_unauthorized(self):
        """인증 없이 조회 시 401 에러"""
        response = self.client.get('/api/v3/django/booth/tables/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reset_tables(self):
        """테이블 리셋 API 테스트"""
        # 인증
        self.client.force_authenticate(user=self.user)

        taget_table_nums = [2, 3]

        tables = Table.objects.filter(booth=self.booth, table_num__in=taget_table_nums)
        tables.update(status=Table.Status.IN_USE)

        # 사용 기록 생성
        for table in tables:
            TableUsage.objects.create(table=table, started_at=now())

        # 리셋 API 호출
        response = self.client.post(
            '/api/v3/django/booth/tables/reset/',
            {'table_nums': taget_table_nums},
            format='json'
        )

        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

        # 테이블 상태 확인
        for table in tables:
            table.refresh_from_db()
            self.assertEqual(table.status, Table.Status.ACTIVE)

        # 사용 기록 종료 확인
        usages = TableUsage.objects.filter(table__in=tables)
        for usage in usages:
            self.assertIsNotNone(usage.ended_at)
            self.assertIsNotNone(usage.usage_minutes)
    
    def test_reset_merged_tables(self):
        """병합된 테이블 리셋 API 테스트"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            '/api/v3/django/booth/tables/merge/',
            {'table_nums': [1, 2, 3]},
            format='json'
        )

        # 이거 대표만 번호 받아야함.
        response = self.client.post(
            '/api/v3/django/booth/tables/reset/',
            {'table_nums': [1]},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

        table_1 = Table.objects.get(booth=self.booth, table_num=1)
        table_2 = Table.objects.get(booth=self.booth, table_num=2)
        table_3 = Table.objects.get(booth=self.booth, table_num=3)

        self.assertEqual(table_1.status, Table.Status.ACTIVE)
        self.assertEqual(table_2.status, Table.Status.ACTIVE)
        self.assertEqual(table_3.status, Table.Status.ACTIVE)

        self.assertIsNone(table_1.group)
        self.assertIsNone(table_2.group)
        self.assertIsNone(table_3.group)


    def test_reset_tables_invalid_nums(self):
        """존재하지 않는 테이블 리셋 시도 - 404 에러"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/v3/django/booth/tables/reset/',
            {'table_nums': [8619]},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_merge_tables(self):
        """테이블 병합 API 테스트"""

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/v3/django/booth/tables/merge/',
            {'table_nums': [1, 2, 3]},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

        # TableGroup 생성 확인
        self.assertEqual(TableGroup.objects.count(), 1)
        group = TableGroup.objects.first()

        # 대표 테이블 번호 확인 낮은 번호여야함
        self.assertEqual(group.representative_table.table_num, 1)

        # 테이블 병합 테스트 같은 Group id를 가져야함
        table_1 = Table.objects.get(booth=self.booth, table_num=1)
        table_2 = Table.objects.get(booth=self.booth, table_num=2)
        table_3 = Table.objects.get(booth=self.booth, table_num=3)

        self.assertEqual(table_1.group, group)
        self.assertEqual(table_2.group, group)
        self.assertEqual(table_3.group, group)

    def test_merge_representive_tables(self):
        self.client.force_authenticate(user=self.user)
        logger.info("\n ================================= 테스트 시작: 대표 테이블 병합 테스트 1 / 2 / 3 ================================= \n")
        response = self.client.post(
            '/api/v3/django/booth/tables/merge/',
            {'table_nums': [1, 2, 3]},
            format='json'
        )
        logger.info("\n ================================= 테스트 시작: 대표 테이블 병합 테스트 4 / 5 / 6 ================================= \n")
        response = self.client.post(
            '/api/v3/django/booth/tables/merge/',
            {'table_nums': [4, 5, 6]},
            format='json'
        )
        logger.info("\n ================================= 테스트 시작: 대표 테이블 병합 테스트 1, 4 병합 ================================= \n")
        response = self.client.post(
            '/api/v3/django/booth/tables/merge/',
            {'table_nums': [1, 4]},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('테이블이 병합되었습니다.', response.data.get('message', ''))

        # 응답 data 검증
        data = response.data.get('data', {})
        self.assertEqual(data.get('merge_table_cnt'), 6)

        # TableGroup 생성 확인 / 기존 그룹 삭제임
        self.assertEqual(TableGroup.objects.count(), 1)
        group = TableGroup.objects.first()

        # 대표 테이블 번호 확인 낮은 번호여야함 / 지금 검증에선 1
        self.assertEqual(group.representative_table.table_num, 1)
        self.assertEqual(data.get('representive'), group.representative_table.id)

        # 테이블 병합 테스트 같은 Group id를 가져야함
        merged_tables = Table.objects.filter(booth=self.booth, table_num__in=[1, 2, 3, 4, 5, 6])

        for table in merged_tables:
            self.assertEqual(table.group, group)
        
        
        