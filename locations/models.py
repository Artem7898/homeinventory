from django.db import models



class Location(models.Model):
    name = models.CharField('Название', max_length=100)
    description = models.TextField('Описание', blank=True)

    class Meta:
        verbose_name = 'Место хранения'
        verbose_name_plural = 'Места хранения'

    def __str__(self):
        return self.name