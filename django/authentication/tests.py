import logging
from contextlib import contextmanager

from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

from booth.models import Booth


@contextmanager
def suppress_request_warnings():
    """의도적인 Bad Request 테스트 시 로그 억제"""
    logger = logging.getLogger('django.request')
    previous_level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(previous_level)


class SignupViewTest(APITestCase):
    """회원가입 API 테스트"""

    def setUp(self):
        self.signup_url = '/api/v3/auth/signup/'
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

    def test_signup_success(self):
        """회원가입 성공 테스트"""
        response = self.client.post(
            self.signup_url,
            self.valid_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='testuser').exists())
        self.assertTrue(Booth.objects.filter(name='테스트 부스').exists())

    def test_signup_sets_cookies(self):
        """회원가입 시 JWT 쿠키 설정 테스트"""
        response = self.client.post(
            self.signup_url,
            self.valid_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)

    def test_signup_duplicate_username(self):
        """중복 username 회원가입 실패 테스트"""
        User.objects.create_user(username='testuser', password='existingpass')

        with suppress_request_warnings():
            response = self.client.post(
                self.signup_url,
                self.valid_data,
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_missing_username(self):
        """username 누락 시 실패 테스트"""
        invalid_data = self.valid_data.copy()
        del invalid_data['username']

        with suppress_request_warnings():
            response = self.client.post(
                self.signup_url,
                invalid_data,
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_missing_password(self):
        """password 누락 시 실패 테스트"""
        invalid_data = self.valid_data.copy()
        del invalid_data['password']

        with suppress_request_warnings():
            response = self.client.post(
                self.signup_url,
                invalid_data,
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_missing_booth_data(self):
        """booth_data 누락 시 실패 테스트"""
        invalid_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }

        with suppress_request_warnings():
            response = self.client.post(
                self.signup_url,
                invalid_data,
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_creates_booth_with_user(self):
        """회원가입 시 User와 Booth가 연결되는지 테스트"""
        response = self.client.post(
            self.signup_url,
            self.valid_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username='testuser')
        booth = Booth.objects.get(user=user)

        self.assertEqual(booth.name, '테스트 부스')
        self.assertEqual(booth.table_max_cnt, 10)
        self.assertEqual(booth.bank, '신한은행')

class CheckUsernameViewTest(APITestCase):
    def setUp(self):
        self.username_check_url = '/api/v3/auth/check-username/'
        User.objects.create_user(username='existinguser', password='testpass')

    def test_username_parameter_missing(self):
        """username 파라미터 누락 시 실패 테스트"""
        with suppress_request_warnings():
            response = self.client.get(self.username_check_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_username_available(self):
        """사용 가능한 username 체크 테스트"""
        response = self.client.get(
            self.username_check_url,
            {'username': 'newuser'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['data']['is_available'])

    def test_username_unavailable(self):
        """사용 불가능한 username 체크 테스트"""
        response = self.client.get(
            self.username_check_url,
            {'username': 'existinguser'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['data']['is_available'])


class AuthApiViewTest(APITestCase):
    def setUp(self):
        self.auth_url = '/api/v3/auth/'
        self.username = 'testuser'
        self.password = 'testpass123'
        User.objects.create_user(username=self.username, password=self.password)

    def test_login_success(self):
        """로그인 성공 테스트"""
        response = self.client.post(
            self.auth_url,
            {
                'username': self.username,
                'password': self.password
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)    

    def test_login_invalid_username(self):
        """잘못된 username 로그인 실패 테스트"""
        with suppress_request_warnings():
            response = self.client.post(
                self.auth_url,
                {
                    'username': 'wronguser',
                    'password': self.password
                },
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_invalid_password(self):
        """잘못된 password 로그인 실패 테스트"""
        with suppress_request_warnings():
            response = self.client.post(
                self.auth_url,
                {
                    'username': self.username,
                    'password': 'wrongpass'
                },
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_verify_success(self):
        """토큰 유효성 확인 성공 테스트"""
        # 먼저 로그인하여 토큰 획득
        login_response = self.client.post(
            self.auth_url,
            {
                'username': self.username,
                'password': self.password
            },
            format='json'
        )

        access_token = login_response.cookies.get('access_token').value

        # 토큰 유효성 확인 요청
        response = self.client.get(
            self.auth_url,
            HTTP_COOKIE=f'access_token={access_token}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['username'], self.username)

    def test_token_verify_missing_token(self):
        """토큰 없이 유효성 확인 시 실패 테스트"""
        with suppress_request_warnings():
            response = self.client.get(self.auth_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout_success(self):
        """로그아웃 성공 테스트"""
        # 먼저 로그인하여 토큰 획득
        login_response = self.client.post(
            self.auth_url,
            {
                'username': self.username,
                'password': self.password
            },
            format='json'
        )

        response = self.client.delete(
            self.auth_url,
            HTTP_COOKIE=(
                f"access_token={login_response.cookies.get('access_token').value}; "
                f"refresh_token={login_response.cookies.get('refresh_token').value}"
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # delete_cookie는 값을 비우고 max-age=0으로 설정하여 브라우저가 삭제하도록 함
        self.assertEqual(response.cookies['access_token'].value, '')
        self.assertEqual(response.cookies['access_token']['max-age'], 0)
        self.assertEqual(response.cookies['refresh_token'].value, '')
        self.assertEqual(response.cookies['refresh_token']['max-age'], 0)
    
    