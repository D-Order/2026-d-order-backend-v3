"""
JWT 쿠키 기반 인증 + CSRF 보호

- 쿠키에서 JWT 토큰 읽기
- POST/PUT/PATCH/DELETE 요청 시 CSRF 자동 체크
- Django의 CSRF 설정을 그대로 활용
"""
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class JWTCookieAuthentication(JWTAuthentication):
    """
    JWT 쿠키 인증 + CSRF 보호

    동작:
    1. Authorization 헤더 확인
    2. 헤더 없으면 쿠키에서 access_token 읽기
    3. JWT 토큰 검증
    4. POST/PUT/PATCH/DELETE 시 CSRF 자동 체크
    """

    def authenticate(self, request):
        """
        JWT 토큰 인증 + CSRF 체크

        Returns:
            tuple: (user, validated_token) 또는 None
        """
        # 1. Authorization 헤더 확인
        header = self.get_header(request)

        if header is None:
            # 2. 헤더 없으면 쿠키에서 토큰 가져오기
            raw_token = request.COOKIES.get('access_token')
            if raw_token is None:
                logger.debug("[JWTCookieAuth] No token in header or cookie")
                return None
        else:
            raw_token = self.get_raw_token(header)

        if raw_token is None:
            return None

        # 3. JWT 토큰 검증
        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            logger.debug(f"[JWTCookieAuth] Token validated for user: {user.username}")
        except Exception as e:
            logger.warning(f"[JWTCookieAuth] Token validation failed: {e}")
            return None

        # 4. Unsafe 메서드는 CSRF 체크
        if request.method not in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            self._enforce_csrf(request)

        return (user, validated_token)

    def _enforce_csrf(self, request):
        """
        CSRF 토큰 검증

        Django의 CsrfViewMiddleware를 사용하여
        settings.py의 CSRF 설정을 그대로 활용

        Raises:
            PermissionDenied: CSRF 검증 실패 시
        """
        def dummy_get_response(request):
            return None

        check = CsrfViewMiddleware(dummy_get_response)

        # CSRF 체크 실행
        check.process_request(request)
        reason = check.process_view(request, None, (), {})

        if reason:
            logger.warning(f"[JWTCookieAuth] CSRF check failed: {reason}")
            raise PermissionDenied(f'CSRF verification failed: {reason}')

        logger.debug(f"[JWTCookieAuth] CSRF check passed for {request.method} {request.path}")
