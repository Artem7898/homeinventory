from django.contrib import admin
from workspaces.admin import WorkspaceScopedAdmin
from .models import Container, Item, Loan, Movement, PublicListing


@admin.action(description='Экспортировать выбранное в CSV', permissions=['view'])
def export_to_csv(modeladmin, request, queryset):
    from .csv_export import csv_response
    return csv_response(queryset.select_related('category', 'location', 'container__location'), filename='inventory_export.csv')


@admin.register(Item)
class ItemAdmin(WorkspaceScopedAdmin):
    list_display = ['name', 'workspace', 'category', 'location', 'container', 'price', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['label_id', 'version', 'created_at', 'updated_at', 'search_text', 'qr_code']
    actions = [export_to_csv]
    list_select_related = ['workspace', 'category', 'location', 'container']


@admin.register(Container)
class ContainerAdmin(WorkspaceScopedAdmin):
    list_display = ['name', 'workspace', 'location']
    readonly_fields = ['label_id', 'version']


@admin.register(PublicListing)
class PublicListingAdmin(WorkspaceScopedAdmin):
    list_display = ['title', 'workspace', 'active']
    readonly_fields = ['token']

    def has_change_permission(self, request, obj=None):
        from workspaces.access import can_manage
        return super().has_change_permission(request, obj) and (obj is None or can_manage(request.user, obj.workspace))

    def has_add_permission(self, request):
        return request.user.is_superuser


@admin.register(Loan)
class LoanAdmin(WorkspaceScopedAdmin):
    list_display = ['item', 'workspace', 'borrower', 'opened_at', 'returned_at']
    readonly_fields = ['workspace', 'item', 'borrower', 'opened_by', 'opened_at', 'due_date', 'returned_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Movement)
class MovementAdmin(WorkspaceScopedAdmin):
    list_display = ['workspace', 'item', 'container', 'actor', 'created_at']
    readonly_fields = ['workspace', 'item', 'container', 'from_location', 'to_location', 'actor', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
