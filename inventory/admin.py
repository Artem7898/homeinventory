# inventory/admin.py
from django.contrib import admin
from django.contrib.admin import display
from django.utils.html import format_html
from django.http import HttpResponse
from unfold.admin import ModelAdmin  # ВАЖНО: используем ModelAdmin от Unfold
from inventory.models import Item
from categories.models import Category
from locations.models import Location


# Экспорт CSV как действие
def export_to_csv(modeladmin, request, queryset):
    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="inventory_export.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Название', 'Категория', 'Место', 'Цена', 'Дата'])

    for item in queryset:
        writer.writerow([
            item.name,
            item.category.name if item.category else '-',
            item.location.name if item.location else '-',
            item.price or 0,
            item.purchase_date or '-'
        ])

    return response


export_to_csv.short_description = '📥 Экспортировать в CSV'


# Кастомная админка для Item
@admin.register(Item)
class ItemAdmin(ModelAdmin):  # Наследуется от unfold.admin.ModelAdmin
    list_display = ['name', 'category', 'location', 'price_preview', 'qr_preview', 'created_at']
    list_filter = ['category', 'location', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['qr_preview_large']
    actions = [export_to_csv]

    def has_delete_permission(self, request, obj=None):
        """Разрешить удаление"""
        return True

    def get_actions(self, request):
        """Кастомизация действий"""
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            actions['delete_selected'][0].short_description = '🗑️ Удалить выбранные вещи'
        return actions

    @display(description='QR')
    def qr_preview(self, obj):
        if obj.qr_code:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px;" />',
                obj.qr_code.url
            )
        return '-'

    @display(description='Цена')
    def price_preview(self, obj):
        if obj.price:
            return f'{obj.price}₽'
        return '-'

    def qr_preview_large(self, obj):
        if obj.qr_code:
            return format_html(
                '<img src="{}" style="max-width: 300px;" /><br>'
                '<a href="{}" download class="btn">Скачать QR</a>',
                obj.qr_code.url,
                obj.qr_code.url
            )
        return 'QR-код не сгенерирован'

    qr_preview_large.short_description = 'QR-код'


# Регистрация остальных моделей
@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ['name']

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(Location)
class LocationAdmin(ModelAdmin):
    list_display = ['name']

    def has_delete_permission(self, request, obj=None):
        return True