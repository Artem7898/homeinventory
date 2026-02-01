"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import RedirectView

# Временная заглушка для API
def api_documentation(request):
    """Документация API (временно отключено)"""
    return JsonResponse({
        'status': 'success',
        'message': 'Домашний инвентарь API',
        'version': '1.0.0',
        'description': 'API временно отключено для настройки Railway',
        'endpoints': {
            'home': '/',
            'scanner': '/scanner/',
            'export': '/export/',
            'item_detail': '/item/{id}/',
            'search': '/search/?q=query',
            'admin': f'/{settings.ADMIN_URL}/'
        }
    })

def admin_search(request):
    """Поиск для админки"""
    return JsonResponse({'results': []})

urlpatterns = [
    # API заглушка
    path('api/', api_documentation, name='api-root'),
    
    # Админка
    path('admin/search/', admin_search, name='admin_search'),
    path('admin/', admin.site.urls)
    
    # Основные приложения
    path('', include('inventory.urls')),
    
    # Редирект для favicon (чтобы не было 404 ошибок)
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
]

# Только для разработки (DEBUG=True)
if settings.DEBUG:
    # Django Debug Toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
    
    # Статические и медиа файлы
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # В production на Railway статические файлы обслуживаются через Whitenoise
    # Нужно создать файл 404.html и 500.html в templates/
    handler404 = 'inventory.views.page_not_found'
    handler500 = 'inventory.views.server_error'

# Безопасный редирект для www и https (опционально)
if not settings.DEBUG:
    # Принудительный HTTPS редирект (Railway сам делает SSL)
    # Можно включить, если нужно
    # urlpatterns = [path('', include('django_ssl_redirect.urls'))] + urlpatterns
    pass
