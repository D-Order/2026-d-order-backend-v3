from django.urls import path
from .views import *

urlpatterns = [
    path("mypage/", BoothMyPageAPIView.as_view(), name="mypage"),
    path("mypage/qr-download/", BoothMyPageQRcodeAPIView.as_view(), name="mypage-qrcode"),
    path("<uuid:booth_uuid>/name/", BoothNameAPIView.as_view(), name="name"),
    # TODO: 테스트용 - 운영 환경에서는 제거 또는 권한 강화 필요
    path("mypage/reset-table-data/", BoothTableUsageResetAPIView.as_view(), name="reset-table-data"),
]
