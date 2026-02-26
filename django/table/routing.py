from django.urls import re_path
from .consumers import TableConsumer

websocket_urlpatterns = [
    re_path(r'ws/django/booth/tables/', TableConsumer.as_asgi()),
]