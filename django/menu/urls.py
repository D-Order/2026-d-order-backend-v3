from django.urls import path
from .views import MenuAPIView, MenuDetailAPIView, SetMenuAPIView, SetMenuDetailAPIView, BoothMenuListAPIView, UserMenuListAPIView

urlpatterns = [
    # Menu CRUD
    path('menus/', MenuAPIView.as_view(), name='menu-create'),
    path('menus/<int:menu_id>/', MenuDetailAPIView.as_view(), name='menu-detail'),
    
    # SetMenu CRUD
    path('sets/', SetMenuAPIView.as_view(), name='setmenu-create'),
    path('sets/<int:set_id>/', SetMenuDetailAPIView.as_view(), name='setmenu-detail'),
    
    # 전체 메뉴판 조회
    path('menu-list/', BoothMenuListAPIView.as_view(), name='booth-menu-list'),
    path('<int:booth_id>/menu-list/', UserMenuListAPIView.as_view()),
]
