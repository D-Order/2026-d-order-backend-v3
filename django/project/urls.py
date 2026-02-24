"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

from django.conf.urls.static import static

from .views import health_check

urlpatterns = [
    path('django/admin/', admin.site.urls),
    path('api/v3/django/auth/', include('authentication.urls')),
    path('api/v3/django/booth/', include('booth.urls')),
    path('api/v3/django/booth/', include('table.urls')),
    path('api/v3/django/booth/', include('menu.urls')),
    path('api/v3/django/cart/', include('cart.urls')),
    path('api/v3/django/coupon/', include('coupon.urls')),
    path('health/', health_check),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.IS_LOCAL:
    urlpatterns += [path('api/v3/django/silk/', include('silk.urls', namespace='silk'))]