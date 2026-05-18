from django.urls import path
from .views import *

urlpatterns = [
    path("mypage/", BoothMyPageAPIView.as_view(), name="mypage"),
    path("mypage/qr-download/", BoothMyPageQRcodeAPIView.as_view(), name="mypage-qrcode"),
    path("<uuid:booth_uuid>/name/", BoothNamePublicAPIView.as_view(), name="name"),
    path("name/", BoothNameAPIView.as_view(), name="name"),
    path("mypage/reset-table-data/", BoothTableUsageResetAPIView.as_view(), name="reset-table-data"),
]
