"""Delete unreferenced uploads only after the database transaction commits."""

import logging

from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Item

logger = logging.getLogger(__name__)


def _remove_unreferenced(storage, name):
    if not name or Item.objects.filter(Q(photo=name) | Q(qr_code=name)).exists():
        return
    try:
        storage.delete(name)
    except (OSError, ValueError):
        logger.warning("Could not remove an unreferenced inventory file; run storage maintenance.")


@receiver(pre_save, sender=Item)
def remember_previous_uploads(sender, instance, **kwargs):
    instance._previous_uploads = []
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).only("photo", "qr_code").first()
        if old:
            for name in ("photo", "qr_code"):
                previous, current = getattr(old, name), getattr(instance, name)
                if previous and previous.name != current.name:
                    instance._previous_uploads.append((previous.storage, previous.name))


@receiver(post_save, sender=Item)
def remove_replaced_uploads(sender, instance, **kwargs):
    for storage, name in getattr(instance, "_previous_uploads", []):
        transaction.on_commit(lambda storage=storage, name=name: _remove_unreferenced(storage, name))


@receiver(post_delete, sender=Item)
def remove_deleted_uploads(sender, instance, **kwargs):
    for field in (instance.photo, instance.qr_code):
        if field:
            transaction.on_commit(
                lambda storage=field.storage, name=field.name: _remove_unreferenced(storage, name)
            )
