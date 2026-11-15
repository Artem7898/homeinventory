from django.contrib import admin
from workspaces.admin import WorkspaceScopedAdmin
from .models import Location


@admin.register(Location)
class LocationAdmin(WorkspaceScopedAdmin):
    list_display = ['name', 'workspace', 'parent']
    list_select_related = ['workspace', 'parent']
