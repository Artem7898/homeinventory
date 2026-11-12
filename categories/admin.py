from django.contrib import admin
from workspaces.admin import WorkspaceScopedAdmin
from .models import Category


@admin.register(Category)
class CategoryAdmin(WorkspaceScopedAdmin):
    list_display = ['name', 'workspace']
    list_select_related = ['workspace']
