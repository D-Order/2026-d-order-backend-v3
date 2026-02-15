from django.urls import path
from .views import *

urlpatterns = [
    path("mypage/", BoothMyPageAPIView.as_view(), name="mypage"),
    path("mypage/qr-download/", BoothMyPageQRcodeAPIView.as_view(), name="mypage-qrcode"),
    path("<int:booth_id>/name/", BoothNameAPIView.as_view(), name="name"),
]
