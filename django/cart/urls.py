from django.urls import path
from .views import *

urlpatterns = [
    path("", CartAddAPIView.as_view(), name="cart-add"),
    path("detail/", CartDetailAPIView.as_view(), name="cart-detail"),
    path("menu/", CartUpdateQuantityAPIView.as_view(), name="cart-update-quantity"),
    path("menu/delete/", CartDeleteItemAPIView.as_view(), name="cart-delete-item"),
    path("payment-info/", CartPaymentInfoAPIView.as_view(), name="cart-payment-info"),
]