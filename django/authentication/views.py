"""
인증 관련 View (HTTP 요청/응답만 처리) 나머지는 service로 분리함
"""
import logging
from django.conf import settings
import jwt
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
import jwt
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from authentication.services import AuthService
from authentication.utils import set_jwt_cookies, delete_jwt_cookies
from authentication.serializers import UserBoothSignupSerializer

logger = logging.getLogger(__name__)


class SignupAPIView(APIView):
    """회원가입"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        """회원가입 처리"""
        username = request.data.get("username", "")
        logger.info("[Signup] 회원가입 요청 수신 | username=%s", username)

        # 1. 입력 검증 (Serializer)
        serializer = UserBoothSignupSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "[Signup] 입력값 검증 실패 | username=%s | errors=%s",
                username, serializer.errors
            )
            return Response({
                "message": "회원가입에 실패했습니다.",
                "data": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        logger.debug("[Signup] 입력값 검증 통과 | username=%s", username)

        try:
            # 2. 회원가입 처리 (Service)
            user = AuthService.signup_user(
                username=serializer.validated_data['username'],
                password=serializer.validated_data['password'],
                booth_data=serializer.validated_data['booth_data']
            )

            # 3. 토큰 발급 (Service)
            tokens = AuthService.issue_tokens(user)

            # 4. 응답 생성
            response = Response({
                "message": "회원가입이 완료되었습니다.",
                "data": {
                    "username": user.username,
                    "booth_id": user.id,
                },
            }, status=status.HTTP_201_CREATED)

            # 5. 쿠키 설정 (Utils)
            set_jwt_cookies(
                response,
                access_token=tokens['access_token'],
                refresh_token=tokens['refresh_token']
            )

            logger.info("[Signup] 회원가입 완료 | username=%s | user_id=%s", user.username, user.id)
            return response

        except ValueError as e:
            logger.warning("[Signup] 회원가입 거부 | username=%s | reason=%s", username, str(e))
            return Response({
                "message": str(e),
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("[Signup] 예상치 못한 오류 발생 | username=%s", username)
            return Response({
                "message": "서버 오류가 발생했습니다.",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckUsernameAPIView(APIView):
    """아이디 중복 체크"""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get(self, request):
        """아이디 사용 가능 여부 확인"""
        username = request.query_params.get("username")

        if not username:
            return Response({
                "message": "username 파라미터가 필요합니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Service 호출
        is_available = AuthService.check_username_available(username)

        return Response({
            "message": "아이디 중복체크에 성공했습니다.",
            "data": {
                "is_available": is_available
            }
        }, status=status.HTTP_200_OK)


class AuthAPIView(APIView):
    """로그인 / 로그아웃"""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        """로그인 처리"""
        username = request.data.get("username")
        password = request.data.get("password")

        try:
            # 1. 로그인 (Service)
            user = AuthService.login_user(username, password)

            # 2. 토큰 발급 (Service)
            tokens = AuthService.issue_tokens(user)

            # 3. 응답 생성
            response = Response({
                "message": "로그인 성공",
                "data": {
                    "username": user.username,
                    "booth_id": user.id
                }
            }, status=status.HTTP_200_OK)

            # 4. 쿠키 설정 (Utils)
            set_jwt_cookies(
                response,
                access_token=tokens['access_token'],
                refresh_token=tokens['refresh_token']
            )

            return response

        except ValueError as e:
            return Response({
                "message": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """로그아웃 처리"""
        response = Response({
            "message": "로그아웃 성공"
        }, status=status.HTTP_200_OK)

        # 쿠키 삭제 (Utils)
        delete_jwt_cookies(response)

        return response


class TokenRefreshAPIView(APIView):
    """토큰 검증 & 재발급"""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        """토큰 검증 또는 재발급"""

        jwt_settings = settings.SIMPLE_JWT
        access_token = request.COOKIES.get(jwt_settings.get('AUTH_COOKIE'))

        # 1. Access Token 검증
        if access_token:
            try:
                user = AuthService.verify_access_token(access_token)

                return Response({
                    "message": "Access 토큰 유효",
                    "data": {
                        "username": user.username,
                        "booth_id": user.pk,
                    }
                }, status=status.HTTP_200_OK)

            except jwt.ExpiredSignatureError:
                pass  # 만료 → 아래에서 refresh token으로 재발급

            except jwt.InvalidTokenError:
                return Response({
                    "message": "Access 토큰이 유효하지 않음"
                }, status=status.HTTP_401_UNAUTHORIZED)

        # 2. Refresh Token으로 재발급
        refresh_token = request.COOKIES.get(jwt_settings.get('AUTH_COOKIE_REFRESH'))
        if not refresh_token:
            return Response({
                "message": "Refresh 토큰 없음"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            # Service 호출
            tokens = AuthService.refresh_tokens(refresh_token)

            response = Response({
                "message": "Access 토큰 재발급 완료",
                "data": {
                    "username": tokens['user'].username,
                    "booth_id": tokens['user'].pk,
                }
            }, status=status.HTTP_200_OK)

            # 쿠키 설정 (Utils)
            set_jwt_cookies(
                response,
                access_token=tokens['access_token'],
                refresh_token=tokens['refresh_token']
            )

            return response

        except Exception:
            return Response({
                "message": "Refresh 토큰이 유효하지 않음"
            }, status=status.HTTP_401_UNAUTHORIZED)


class CsrfTokenView(APIView):
    """
    CSRF 토큰 발급

    GET /api/v3/auth/csrf-token/

    POST/PUT/PATCH/DELETE 요청 시 X-CSRFToken 헤더에 포함 필요
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get(self, request):
        """CSRF 토큰 발급"""
        csrf_token = get_token(request)
        return Response({
            "csrfToken": csrf_token
        }, status=status.HTTP_200_OK)
