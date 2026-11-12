from .models import Membership, Workspace


def accessible_workspaces(user):
    if not user.is_authenticated or not user.is_active:
        return Workspace.objects.none()
    if user.is_superuser:
        return Workspace.objects.all()
    return Workspace.objects.filter(memberships__user=user).distinct()


def membership_for(user, workspace):
    if not user.is_authenticated or not user.is_active or workspace is None:
        return None
    return Membership.objects.filter(user=user, workspace=workspace).first()


def can_edit(user, workspace):
    if not user.is_authenticated or not user.is_active or workspace is None:
        return False
    if user.is_superuser:
        return True
    member = membership_for(user, workspace)
    return member is not None and member.role in (Membership.Role.OWNER, Membership.Role.EDITOR)


def can_manage(user, workspace):
    if not user.is_authenticated or not user.is_active or workspace is None:
        return False
    if user.is_superuser:
        return True
    member = membership_for(user, workspace)
    return member is not None and member.role == Membership.Role.OWNER


def active_workspace(request):
    spaces = accessible_workspaces(request.user)
    selected = request.session.get('workspace_id')
    try:
        workspace = spaces.filter(pk=selected).first() if selected else None
    except (ValueError, TypeError):
        workspace = None
    if workspace is None:
        workspace = spaces.first()
    if workspace is not None:
        request.session['workspace_id'] = workspace.pk
    return workspace
