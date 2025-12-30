"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from django.http import JsonResponse
from inventory.api_urls import api
from inventory.decorators import secure_admin_login
from django.contrib.auth import views as auth_views




def admin_search(request):
    return JsonResponse({'results': []})



urlpatterns = [
    path('admin/search/', admin_search, name='admin_search'),
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    path('', include('inventory.urls')),
    path('api/', include('inventory.api_urls')),
    path('admin/login/', secure_admin_login(auth_views.LoginView.as_view())),
    # Настоящая админка (только ты знаешь путь):
    path(f'{settings.ADMIN_URL}/', admin.site.urls),
]


# Для разработки: serving media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Добавляем debug toolbar ТОЛЬКО в режиме DEBUG
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)