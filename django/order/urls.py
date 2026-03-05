from django.urls import path
from .views import OrderCancelAPIView, OrderItemStatusUpdateAPIView, OrderItemCancelAPIView, TableOrderHistoryAPIView

urlpatterns = [
    path('cancel/', OrderCancelAPIView.as_view(), name='order-cancel'),
    path('status/', OrderItemStatusUpdateAPIView.as_view(), name='order-item-status'),
    path('<int:orderitem_id>/cancel/', OrderItemCancelAPIView.as_view(), name='order-item-cancel'),
    path('table/<int:table_usage_id>/', TableOrderHistoryAPIView.as_view(), name='table-order-history'),
]
