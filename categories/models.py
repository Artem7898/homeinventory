from django.db import models



class Category(models.Model):
    name = models.CharField('Название', max_length=100)
    icon = models.CharField('Иконка', max_length=50, blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name