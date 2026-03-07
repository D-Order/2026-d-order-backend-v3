from django.urls import re_path
from .consumers import CustomerCartConsumer

websocket_urlpatterns = [
    re_path(r"ws/django/cart/(?P<table_usage_id>\d+)/$", CustomerCartConsumer.as_asgi()),
]