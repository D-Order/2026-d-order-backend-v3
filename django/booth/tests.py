from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal

from booth.models import Booth
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
        response = self.client.get('/api/v3/booth/mypage/')

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
        response = self.client.get('/api/v3/booth/mypage/')

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
            '/api/v3/booth/mypage/',
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
            '/api/v3/booth/mypage/',
            data=patch_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)





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
            '/api/v3/auth/signup/',
            data=signup_data,
            format='json'
        )

        self.assertEqual(signup_response.status_code, status.HTTP_201_CREATED)

        # 2. 생성된 User로 인증
        user = User.objects.get(username='newuser')
        self.client.force_authenticate(user=user)

        # 3. 부스 데이터 조회
        response = self.client.get('/api/v3/booth/mypage/')

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
