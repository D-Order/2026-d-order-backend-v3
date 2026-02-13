from django.urls import path
from .views import *

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("", AuthApiView.as_view(), name="auth"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("check-username/", CheckUsernameView.as_view(), name="check-username"),
    path("csrf-token/", CsrfTokenView.as_view(), name="csrf-token"),
]
