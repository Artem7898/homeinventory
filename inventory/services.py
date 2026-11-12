"""Permission-checked, transactional operations shared by web and command flows."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from workspaces.access import can_edit
from .models import Container, Item, Loan, Movement


def _require_editor(actor, workspace):
    if not can_edit(actor, workspace):
        raise PermissionDenied('Недостаточно прав для изменения пространства.')


def _version_update(model, instance, changes, expected_version):
    expected = instance.version if expected_version is None else expected_version
    changed = model.objects.filter(pk=instance.pk, workspace_id=instance.workspace_id, version=expected).update(version=F('version') + 1, **changes)
    if not changed:
        raise ValidationError('Запись уже изменена другим участником. Обновите страницу.')
    instance.refresh_from_db()
    return instance


@transaction.atomic
def move_item(item, *, actor, location=None, container=None, expected_version=None):
    item = Item.objects.select_for_update().get(pk=item.pk)
    _require_editor(actor, item.workspace)
    previous_location = item.effective_location
    item.location = location
    item.container = container
    item.full_clean(validate_unique=False, validate_constraints=False)
    _version_update(Item, item, {'location_id': item.location_id, 'container_id': item.container_id, 'updated_at': timezone.now()}, expected_version)
    Movement.objects.create(workspace=item.workspace, item=item, from_location=previous_location, to_location=item.effective_location, actor=actor)
    return item


@transaction.atomic
def move_container(container, *, actor, location, expected_version=None):
    container = Container.objects.select_for_update().get(pk=container.pk)
    _require_editor(actor, container.workspace)
    previous_location = container.location
    container.location = location
    container.full_clean(validate_unique=False, validate_constraints=False)
    _version_update(Container, container, {'location_id': container.location_id}, expected_version)
    Movement.objects.create(workspace=container.workspace, container=container, from_location=previous_location, to_location=container.location, actor=actor)
    return container


@transaction.atomic
def checkout_item(item, *, actor, borrower, due_date=None):
    item = Item.objects.select_for_update().get(pk=item.pk)
    _require_editor(actor, item.workspace)
    if Loan.objects.filter(item=item, returned_at__isnull=True).exists():
        raise ValidationError('Вещь уже выдана. Сначала оформите возврат.')
    loan = Loan(workspace=item.workspace, item=item, borrower=borrower, opened_by=actor, due_date=due_date)
    loan.full_clean(validate_unique=False, validate_constraints=False)
    try:
        with transaction.atomic():
            loan.save()
    except IntegrityError as exc:
        raise ValidationError('Вещь уже выдана другим участником.') from exc
    return loan


@transaction.atomic
def return_loan(loan, *, actor):
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    _require_editor(actor, loan.workspace)
    if loan.returned_at is None:
        loan.returned_at = timezone.now()
        loan.save(update_fields=['returned_at'])
    return loan
