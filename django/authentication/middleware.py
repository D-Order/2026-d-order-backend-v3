import logging
from http.cookies import SimpleCookie

from channels.middleware import BaseMiddleware
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


class JWTCookieMiddleware:
    """
    HTTP 요청용.
    쿠키의 access_token을 Authorization 헤더로 변환.
    프론트에서 credentials: 'include'로 보내면
    DRF JWTAuthentication이 인식할 수 있게 해줌.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        access_token = request.COOKIES.get('access_token')
        if access_token and 'HTTP_AUTHORIZATION' not in request.META:
            request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
        return self.get_response(request)


@sync_to_async(thread_sensitive=True)
def get_user_from_token(token_str):
    try:
        User = get_user_model()
        token = AccessToken(token_str)
        user = User.objects.get(id=token['user_id'])
        session_id = token.get('session_id')
        logger.debug(f"[JWTWebSocketMiddleware] Token OK → user={user}, session_id={session_id}")
        return user, session_id
    except Exception as e:
        logger.error(f"[JWTWebSocketMiddleware] Invalid token: {e}", exc_info=True)
        return None, None


class JWTWebSocketMiddleware(BaseMiddleware):
    """
    WebSocket 연결용.
    핸드셰이크 시 전송되는 쿠키에서 access_token을 추출하여
    scope["user"]를 설정.
    """
    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode()

        cookies = SimpleCookie(cookie_header)
        access_token = cookies.get("access_token")

        scope["user"] = AnonymousUser()

        if access_token:
            user, session_id = await get_user_from_token(access_token.value)
            if user:
                scope["user"] = user
                scope["session_id"] = session_id
                logger.info(f"[JWTWebSocketMiddleware] Token OK → user set: {user}, session_id={session_id}")
            else:
                logger.warning("[JWTWebSocketMiddleware] Token provided but no valid user found")
        else:
            logger.warning("[JWTWebSocketMiddleware] No token in cookie")

        return await super().__call__(scope, receive, send)
