from django.urls import re_path
from order.consumers import AdminOrderManagementConsumer, BoothSalesConsumer

websocket_urlpatterns = [
    re_path(r'ws/django/booth/orders/management/$', AdminOrderManagementConsumer.as_asgi()),
    re_path(r'ws/django/booth/sales/$', BoothSalesConsumer.as_asgi()),
]
