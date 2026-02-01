from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from ninja import NinjaAPI
from inventory.api import router
from inventory.decorators import secure_admin_login
from django.contrib.auth import views as auth_views


api = NinjaAPI(
    title="HomeInventory API",
    version="1.0.0",
    description="API для сканирования QR-кодов и управления инвентарём",
)
api.add_router("/items/", router)

def admin_search(request):
    return JsonResponse({'results': []})

urlpatterns = [
    path('api/', api.urls),
    path('admin/search/', admin_search, name='admin_search'),
    path('', include('inventory.urls')),
    path(f'{settings.ADMIN_URL}/', admin.site.urls),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
