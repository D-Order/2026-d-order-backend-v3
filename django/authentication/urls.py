from django.urls import path
from .views import *

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("", AuthApiView.as_view(), name="auth"),
    path("refresh/", AuthApiView.as_view(), name="auth-refresh"),
    path("check-username/", CheckUsernameView.as_view(), name="check-username"),
]
