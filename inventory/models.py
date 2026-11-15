import unicodedata
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from workspaces.models import WorkspaceBoundModel


def normalize_search(value):
    return unicodedata.normalize('NFKC', value).casefold()


class Container(WorkspaceBoundModel):
    name = models.CharField('Название коробки', max_length=200)
    description = models.TextField('Описание', blank=True)
    location = models.ForeignKey('locations.Location', on_delete=models.PROTECT, null=True, blank=True, related_name='containers')
    label_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    version = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ['name', 'pk']
        verbose_name = 'Контейнер'
        verbose_name_plural = 'Контейнеры'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('inventory:container-detail', kwargs={'pk': self.pk})

    def get_label_url(self):
        return f'/labels/container/{self.label_id}/'


class Item(WorkspaceBoundModel):
    name = models.CharField('Название вещи', max_length=200)
    description = models.TextField('Описание', blank=True)
    category = models.ForeignKey('categories.Category', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Категория')
    location = models.ForeignKey('locations.Location', on_delete=models.PROTECT, null=True, blank=True, verbose_name='Место хранения')
    container = models.ForeignKey(Container, on_delete=models.PROTECT, null=True, blank=True, related_name='items', verbose_name='Контейнер')
    purchase_date = models.DateField('Дата покупки', null=True, blank=True)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    photo = models.ImageField('Фото', upload_to='items/', blank=True, null=True)
    # Retained for safe upgrades; new QR images are generated on demand.
    qr_code = models.ImageField('Старый QR-код', upload_to='qrcodes/', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    label_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    version = models.PositiveIntegerField(default=0, editable=False)
    search_text = models.TextField(blank=True, editable=False)

    class Meta:
        verbose_name = 'Вещь'
        verbose_name_plural = 'Вещи'
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(check=~(models.Q(location__isnull=False) & models.Q(container__isnull=False)), name='item_has_one_place')]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.location_id and self.container_id:
            raise ValidationError({'container': 'Выберите место или контейнер, а не оба сразу.'})

    def save(self, *args, **kwargs):
        self.search_text = normalize_search(f'{self.name} {self.description}')
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'search_text', 'updated_at'}
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('inventory:item-detail', kwargs={'pk': self.pk}) if self.pk else '/'

    def get_label_url(self):
        return f'/labels/item/{self.label_id}/'

    @property
    def effective_location(self):
        return self.container.location if self.container_id else self.location


class Movement(WorkspaceBoundModel):
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE, related_name='movements')
    container = models.ForeignKey(Container, null=True, blank=True, on_delete=models.CASCADE, related_name='movements')
    from_location = models.ForeignKey('locations.Location', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    to_location = models.ForeignKey('locations.Location', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(check=(models.Q(item__isnull=False, container__isnull=True) | models.Q(item__isnull=True, container__isnull=False)), name='movement_has_one_subject')]


class Loan(WorkspaceBoundModel):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='loans')
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='inventory_loans')
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    opened_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-opened_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['item'], condition=models.Q(returned_at__isnull=True), name='one_active_loan_per_item')]

    def clean(self):
        super().clean()
        if self.borrower_id and self.workspace_id:
            if not self.borrower.workspace_memberships.filter(workspace_id=self.workspace_id).exists():
                raise ValidationError({'borrower': 'Получатель должен быть участником этого пространства.'})


class PublicListing(WorkspaceBoundModel):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='public_listing')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField('Публичное название', max_length=200)
    description = models.TextField('Публичное описание', blank=True)
    active = models.BooleanField('Опубликовано', default=False)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f'/public/{self.token}/'
