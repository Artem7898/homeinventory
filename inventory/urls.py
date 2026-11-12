from django.urls import path
from . import views

app_name = 'inventory'
urlpatterns = [
    path('', views.item_list, name='item-list'),
    path('search/', views.item_list, name='search'),
    path('item/add/', views.item_create, name='item-create'),
    path('item/<int:pk>/', views.item_detail, name='item-detail'),
    path('item/<int:pk>/edit/', views.item_edit, name='item-edit'),
    path('item/<int:pk>/delete/', views.item_delete, name='item-delete'),
    path('item/<int:pk>/qr.png', views.item_qr, name='item-qr'),
    path('item/<int:pk>/checkout/', views.loan_checkout, name='loan-checkout'),
    path('item/<int:pk>/publication/', views.listing_edit, name='listing-edit'),
    path('loans/<int:pk>/return/', views.loan_return, name='loan-return'),
    path('containers/', views.container_list, name='container-list'),
    path('containers/add/', views.container_create, name='container-create'),
    path('containers/<int:pk>/', views.container_detail, name='container-detail'),
    path('containers/<int:pk>/edit/', views.container_edit, name='container-edit'),
    path('containers/<int:pk>/move/', views.container_move, name='container-move'),
    path('containers/<int:pk>/qr.png', views.container_qr, name='container-qr'),
    path('categories/add/', views.category_create, name='category-create'),
    path('locations/add/', views.location_create, name='location-create'),
    path('export/', views.export_csv, name='export-csv'),
    path('scanner/', views.scanner_view, name='scanner'),
    path('labels/', views.labels, name='labels'),
    path('labels/resolve/', views.label_resolve, name='label-resolve'),
    path('labels/item/<uuid:label_id>/', views.item_label, name='item-label'),
    path('labels/container/<uuid:label_id>/', views.container_label, name='container-label'),
    path('public/<uuid:token>/', views.public_listing, name='public-listing'),
]
