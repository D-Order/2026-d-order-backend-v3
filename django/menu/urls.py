from django.urls import path
from .views import MenuAPIView, MenuDetailAPIView

urlpatterns = [
    # Menu CRUD
    path('menus/', MenuAPIView.as_view(), name='menu-create'),
    path('menus/<int:menu_id>/', MenuDetailAPIView.as_view(), name='menu-detail'),
]
