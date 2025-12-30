from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.item_list, name='item-list'),
    path('item/<int:pk>/', views.item_detail, name='item-detail'),
    path('export/', views.export_csv, name='export-csv'),
    path('scanner/', views.scanner_view, name='scanner'),
    path('search/', views.item_list, name='search'),  # ВРЕМЕННАЯ ЗАГЛУШКА
]