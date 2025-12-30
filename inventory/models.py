from django.db import models
from django.urls import reverse
import qrcode
from django.core.files import File
from io import BytesIO


class Item(models.Model):
    name = models.CharField('Название вещи', max_length=200)
    description = models.TextField('Описание', blank=True)
    category = models.ForeignKey('categories.Category', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='Категория')
    location = models.ForeignKey('locations.Location', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='Место хранения')
    purchase_date = models.DateField('Дата покупки', null=True, blank=True)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, null=True, blank=True)
    photo = models.ImageField('Фото', upload_to='items/', blank=True, null=True)
    qr_code = models.ImageField('QR-код', upload_to='qrcodes/', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Вещь'
        verbose_name_plural = 'Вещи'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        if self.pk:
            return reverse('inventory:item-detail', kwargs={'pk': self.pk})
        return '/'

    def generate_qr_code(self):
        """Генерирует QR-код и возвращает имя файла"""
        if not self.pk:
            return  # Не генерируем для новых объектов без ID

        qr_data = f"http://127.0.0.1:8000{self.get_absolute_url()}"
        qr_image = qrcode.make(qr_data)

        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        buffer.seek(0)

        filename = f'item_{self.pk}.png'
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        # Сохраняем один раз, чтобы получить pk
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Генерируем QR только для новых объектов и если его нет
        if is_new and not self.qr_code:
            self.generate_qr_code()
            # Сохраняем ТОЛЬКО поле qr_code
            super().save(update_fields=['qr_code'])