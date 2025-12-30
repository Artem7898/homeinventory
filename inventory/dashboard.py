from django.contrib.admin.sites import AdminSite
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.urls import path
from django.http import HttpRequest


class CustomAdminSite(AdminSite):
    site_header = '📦 Домашний инвентарь'
    site_title = 'Учёт вещей'
    index_title = 'Главная'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
        ]
        return custom_urls + urls

    def dashboard_view(self, request: HttpRequest):
        from inventory.models import Item
        from categories.models import Category
        from locations.models import Location

        stats = {
            'total_items': Item.objects.count(),
            'total_value': Item.objects.aggregate(total=Sum('price'))['total'] or 0,
            'locations_count': Location.objects.count(),
            'categories_count': Category.objects.count(),
            'recent_items': Item.objects.order_by('-created_at')[:5],
        }
        return render(request, 'admin/dashboard.html', stats)


admin_site = CustomAdminSite(name='custom_admin')