from django.db import models
from workspaces.models import WorkspaceBoundModel


class Category(WorkspaceBoundModel):
    name = models.CharField('Название', max_length=100)
    icon = models.CharField('Иконка', max_length=50, blank=True)

    class Meta:
        ordering = ['name', 'pk']
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name
