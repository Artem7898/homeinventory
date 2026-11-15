from django.core.exceptions import ValidationError
from django.db import models
from workspaces.models import WorkspaceBoundModel


class Location(WorkspaceBoundModel):
    name = models.CharField('Название', max_length=100)
    description = models.TextField('Описание', blank=True)
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='children', verbose_name='Родительское место')

    class Meta:
        ordering = ['name', 'pk']
        verbose_name = 'Место хранения'
        verbose_name_plural = 'Места хранения'

    def clean(self):
        super().clean()
        seen = {self.pk} if self.pk else set()
        node = self.parent if self.parent_id else None
        while node is not None:
            if node.pk in seen:
                raise ValidationError({'parent': 'Иерархия мест не может содержать циклы.'})
            seen.add(node.pk)
            if len(seen) > 30:
                raise ValidationError({'parent': 'Слишком глубокая иерархия мест.'})
            node = node.parent

    @property
    def path(self):
        names = [self.name]
        node = self.parent
        seen = {self.pk}
        while node and node.pk not in seen:
            names.append(node.name)
            seen.add(node.pk)
            node = node.parent
        return ' → '.join(reversed(names))

    def __str__(self):
        return self.name
