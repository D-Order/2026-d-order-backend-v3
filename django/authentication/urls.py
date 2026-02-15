from django.urls import path
from .views import *

urlpatterns = [
    path("signup/", SignupAPIView.as_view(), name="signup"),
    path("", AuthAPIView.as_view(), name="auth"),
    path("refresh/", TokenRefreshAPIView.as_view(), name="token-refresh"),
    path("check-username/", CheckUsernameAPIView.as_view(), name="check-username"),
    path("csrf-token/", CsrfTokenView.as_view(), name="csrf-token"),
]
