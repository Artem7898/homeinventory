from django.contrib import admin
from unfold.admin import ModelAdmin

from .access import accessible_workspaces, can_edit
from .models import Membership, Workspace


class WorkspaceScopedAdmin(ModelAdmin):
    """Django permissions AND workspace roles, including foreign-key choices."""
    def get_queryset(self, request):
        return super().get_queryset(request).filter(workspace__in=accessible_workspaces(request.user))

    def _has_editable_space(self, user):
        if not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser:
            return True
        return user.workspace_memberships.filter(role__in=[Membership.Role.OWNER, Membership.Role.EDITOR]).exists()

    def has_add_permission(self, request):
        return super().has_add_permission(request) and self._has_editable_space(request.user)

    def has_change_permission(self, request, obj=None):
        allowed = self._has_editable_space(request.user) if obj is None else can_edit(request.user, obj.workspace)
        return super().has_change_permission(request, obj) and allowed

    def has_delete_permission(self, request, obj=None):
        allowed = self._has_editable_space(request.user) if obj is None else can_edit(request.user, obj.workspace)
        return super().has_delete_permission(request, obj) and allowed

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and (obj is None or accessible_workspaces(request.user).filter(pk=obj.workspace_id).exists())

    def _editable_spaces(self, user):
        if user.is_superuser:
            return Workspace.objects.all()
        return Workspace.objects.filter(memberships__user=user, memberships__role__in=[Membership.Role.OWNER, Membership.Role.EDITOR])

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        spaces = self._editable_spaces(request.user)
        model = db_field.remote_field.model
        if model is Workspace:
            kwargs['queryset'] = spaces
        elif hasattr(model, 'workspace'):
            kwargs['queryset'] = model.objects.filter(workspace__in=spaces)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not can_edit(request.user, obj.workspace):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        super().save_model(request, obj, form, change)

    def delete_queryset(self, request, queryset):
        # A bulk action must not use permissions for some other editable space.
        permitted = queryset.filter(workspace__in=self._editable_spaces(request.user))
        permitted.delete()


class SuperuserAdmin(ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(Workspace)
class WorkspaceAdmin(SuperuserAdmin):
    list_display = ['name', 'kind']


@admin.register(Membership)
class MembershipAdmin(SuperuserAdmin):
    list_display = ['user', 'workspace', 'role']
    list_filter = ['role']
