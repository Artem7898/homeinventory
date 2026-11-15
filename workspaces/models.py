from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Workspace(models.Model):
    class Kind(models.TextChoices):
        HOME = 'home', 'Дом'
        WORKSHOP = 'workshop', 'Мастерская'
        COMMUNITY = 'community', 'Сообщество'

    name = models.CharField('Название', max_length=160)
    kind = models.CharField('Сценарий', max_length=20, choices=Kind.choices, default=Kind.HOME)
    created_at = models.DateTimeField(auto_now_add=True)
    import_key = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)

    class Meta:
        ordering = ['name', 'pk']
        verbose_name = 'Пространство'
        verbose_name_plural = 'Пространства'

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Владелец'
        EDITOR = 'editor', 'Редактор'
        VIEWER = 'viewer', 'Наблюдатель'

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workspace_memberships')
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace', 'user'], name='unique_workspace_member')]

    def __str__(self):
        return f'{self.user} — {self.workspace} ({self.get_role_display()})'


class WorkspaceBoundModel(models.Model):
    """Validate tenant boundaries for ordinary model/admin/form writes.

    Database check constraints cover local invariants; cross-table invariants must
    also be enforced by scoped forms/services. Bulk writes are reserved for trusted
    migrations/imports which validate their complete input before writing.
    """
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        errors = {}
        if self.pk and self.workspace_id:
            original = type(self).objects.filter(pk=self.pk).values_list('workspace_id', flat=True).first()
            if original is not None and original != self.workspace_id:
                errors['workspace'] = 'Перенос записи в другое пространство запрещён.'
        for field in self._meta.fields:
            if field.name == 'workspace' or not isinstance(field, models.ForeignKey):
                continue
            related = getattr(self, field.name, None) if getattr(self, field.attname, None) else None
            if related is not None and hasattr(related, 'workspace_id') and related.workspace_id != self.workspace_id:
                errors[field.name] = 'Запись относится к другому пространству.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)
