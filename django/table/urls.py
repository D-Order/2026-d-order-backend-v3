from django.urls import path, include
from .views import *
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'tables', TableManagementViewSet, basename='tables')

urlpatterns = [
    path("<uuid:booth_uuid>/table/", TableEnterAPIView.as_view(), name="table-enter"),
]

urlpatterns += router.urls
    