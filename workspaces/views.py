from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import accessible_workspaces, can_manage
from .forms import MembershipForm, WorkspaceForm
from .models import Membership, Workspace


def _context(request, workspace=None):
    from inventory.views import navigation
    return navigation(request, workspace)


@login_required
def workspace_list(request):
    return render(request, 'workspaces/workspace_list.html', {**_context(request), 'workspaces': accessible_workspaces(request.user)})


@login_required
def workspace_create(request):
    form = WorkspaceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            workspace = form.save()
            Membership.objects.create(workspace=workspace, user=request.user, role=Membership.Role.OWNER)
        request.session['workspace_id'] = workspace.pk
        messages.success(request, 'Пространство создано. Добавьте место или коробку.')
        return redirect('inventory:item-list')
    return render(request, 'workspaces/workspace_form.html', {**_context(request), 'form': form, 'title': 'Создать пространство'}, status=400 if request.method == 'POST' else 200)


@login_required
@require_POST
def workspace_select(request, pk):
    workspace = get_object_or_404(accessible_workspaces(request.user), pk=pk)
    request.session['workspace_id'] = workspace.pk
    return redirect('inventory:item-list')


@login_required
def members(request, pk):
    workspace = get_object_or_404(accessible_workspaces(request.user), pk=pk)
    if not can_manage(request.user, workspace):
        raise PermissionDenied
    form = MembershipForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            Workspace.objects.select_for_update().get(pk=workspace.pk)
            if not can_manage(request.user, workspace):
                raise PermissionDenied
            existing = Membership.objects.filter(workspace=workspace, user=form.user).first()
            if existing and existing.role == Membership.Role.OWNER and form.cleaned_data['role'] != Membership.Role.OWNER and Membership.objects.filter(workspace=workspace, role=Membership.Role.OWNER).count() <= 1:
                form.add_error('role', 'Нельзя понизить роль последнего владельца.')
            else:
                Membership.objects.update_or_create(workspace=workspace, user=form.user, defaults={'role': form.cleaned_data['role']})
                messages.success(request, 'Участие обновлено.')
                return redirect('workspaces:members', pk=workspace.pk)
    return render(request, 'workspaces/members.html', {**_context(request, workspace), 'members': Membership.objects.filter(workspace=workspace).select_related('user'), 'membership_form': form}, status=400 if request.method == 'POST' else 200)


@login_required
@require_POST
def member_remove(request, pk, member_pk):
    workspace = get_object_or_404(accessible_workspaces(request.user), pk=pk)
    if not can_manage(request.user, workspace):
        raise PermissionDenied
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=workspace.pk)
        if not can_manage(request.user, workspace):
            raise PermissionDenied
        member = get_object_or_404(Membership, pk=member_pk, workspace=workspace)
        if member.role == Membership.Role.OWNER and Membership.objects.filter(workspace=workspace, role=Membership.Role.OWNER).count() <= 1:
            messages.error(request, 'Нельзя удалить последнего владельца.')
            return render(request, 'workspaces/members.html', {**_context(request, workspace), 'members': Membership.objects.filter(workspace=workspace).select_related('user'), 'membership_form': MembershipForm()}, status=400)
        member.delete()
    return redirect('workspaces:members', pk=workspace.pk)
