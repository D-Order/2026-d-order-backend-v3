"""
ASGI config for project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from authentication.middleware import JWTWebSocketMiddleware
from django.conf import settings
import table.routing
import order.routing


if 'PYTEST_CURRENT_TEST' in os.environ or os.environ.get('DJANGO_ENV') == 'test':
    # 테스트 환경에서는 JWT 미들웨어 제거
    websocket_app = URLRouter(
        table.routing.websocket_urlpatterns + order.routing.websocket_urlpatterns
    )
else:
    websocket_app = JWTWebSocketMiddleware(
        URLRouter(
            table.routing.websocket_urlpatterns + order.routing.websocket_urlpatterns
        )
    )
    if not settings.DEBUG:
        websocket_app = AllowedHostsOriginValidator(websocket_app)

# ===== 5단계: ASGI Application 설정 =====
application = ProtocolTypeRouter({
    # HTTP 요청 → Django Views
    "http": django_asgi_app,

    # WebSocket 요청 → Django Consumers
    "websocket": websocket_app,
})