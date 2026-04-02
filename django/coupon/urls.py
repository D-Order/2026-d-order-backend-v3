from django.urls import path
from .views import *

urlpatterns = [
    path("", CouponListCreateAPIView.as_view(), name="coupon-list-create"),  # GET/POST
    path("<int:coupon_id>/detail/", CouponDetailAPIView.as_view(), name="coupon-detail"),
    path("<int:coupon_id>/", CouponDeleteAPIView.as_view(), name="coupon-delete"),
    path("download/", CouponDownloadAPIView.as_view()),
    path("apply-coupon/", CouponApplyAPIView.as_view(), name="coupon-apply-cancel"),  # POST/DELETE
]