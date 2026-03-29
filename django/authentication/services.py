"""
인증 관련 비즈니스 로직
"""
import jwt
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError

class AuthService:

    @staticmethod
    @transaction.atomic  # 중간에 실패할 경우 DB 적용 안함
    def signup_user(username, password, booth_data):
        """
        회원가입 처리 (User + Booth + Menu + Table 생성)

        Args:
            username: 사용자 아이디
            password: 비밀번호
            booth_data: Booth 정보 dict

        Returns:
            user: 생성된 User 객체

        Raises:
            ValueError: 중복된 아이디 등
        """

        # 1. 아이디 중복 체크
        if User.objects.filter(username=username).exists():
            raise ValueError("이미 사용 중인 아이디입니다")

        # 2. User 생성
        user = User.objects.create_user(username=username, password=password)

        from booth.services import BoothService
        booth = BoothService.create_booth_for_user(user, booth_data)

        return user

    @staticmethod
    def issue_tokens(user):
        """
        사용자에게 JWT 토큰을 발급합니다.

        Args:
            user: Django User 객체

        Returns:
            dict: {
                'access_token': str,
                'refresh_token': str
            }
        """
        
        token = TokenObtainPairSerializer.get_token(user)

        return {
            'access_token': str(token.access_token),
            'refresh_token': str(token),
        }

    @staticmethod
    def login_user(username, password):
        """
        사용자 로그인 처리

        Args:
            username: 사용자 아이디
            password: 비밀번호

        Returns:
            user: 인증된 User 객체

        Raises:
            ValueError: 아이디 또는 비밀번호 불일치
        """
        # 1. 아이디 확인
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValueError("일치하지 않는 아이디예요.")

        # 2. 비밀번호 확인
        user = authenticate(username=username, password=password)
        if not user:
            raise ValueError("일치하지 않는 비밀번호예요.")

        return user

    @staticmethod
    def verify_access_token(access_token):
        """
        Access Token 검증

        Args:
            access_token: JWT access token 문자열

        Returns:
            user: User 객체 (토큰이 유효한 경우)

        Raises:
            jwt.ExpiredSignatureError: 토큰 만료
            jwt.InvalidTokenError: 토큰 유효하지 않음
        """
        payload = jwt.decode(
            access_token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        user_id = payload.get("user_id")
        user = get_object_or_404(User, pk=user_id)

        return user

    @staticmethod
    def refresh_tokens(refresh_token):
        """
        Refresh Token으로 새 토큰 발급

        Args:
            refresh_token: JWT refresh token 문자열

        Returns:
            dict: {
                'access_token': str,
                'refresh_token': str,
                'user': User 객체
            }

        Raises:
            TokenError: 토큰이 유효하지 않음
        """
        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)

        new_access = serializer.validated_data["access"]
        new_refresh = serializer.validated_data["refresh"]

        # 사용자 정보 추출
        payload = jwt.decode(new_access, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        user = get_object_or_404(User, pk=user_id)

        return {
            'access_token': new_access,
            'refresh_token': new_refresh,
            'user': user,
        }

    @staticmethod
    def check_username_available(username):
        """
        아이디 중복 체크

        Args:
            username: 확인할 아이디

        Returns:
            bool: 사용 가능하면 True, 중복이면 False
        """
        return not User.objects.filter(username=username).exists()
