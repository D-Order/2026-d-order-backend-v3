from django.urls import re_path
from .consumers import TableConsumer, TableDetailConsumer

websocket_urlpatterns = [
    re_path(r'ws/django/booth/tables/(?P<table_num>\d+)/', TableDetailConsumer.as_asgi()),
    re_path(r'ws/django/booth/tables/', TableConsumer.as_asgi()),
]