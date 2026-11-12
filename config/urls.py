"""The application has one private media route in every environment."""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from inventory import views

urlpatterns = [
    path('health/', views.health, name='health'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('api/', views.api_root, name='api-root'),
    path('api/items/<int:pk>/', views.api_item_detail, name='api-item-detail'),
    path('media/<path:path>', views.private_media, name='private-media'),
    path('spaces/', include('workspaces.urls')),
    path('archives/', include('inventory.archive_urls', namespace='archives')),
    path('', include('inventory.urls')),
]

handler400 = 'inventory.views.bad_request'
handler403 = 'inventory.views.permission_denied'
handler404 = 'inventory.views.page_not_found'
handler500 = 'inventory.views.server_error'
