"""Tenant-scoped forms; never trust submitted foreign keys or file metadata."""
import io
import warnings

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models.fields.files import FieldFile
from PIL import Image, ImageOps, UnidentifiedImageError

from categories.models import Category
from locations.models import Location
from .models import Container, Item, PublicListing


def clean_photo(upload):
    if upload is None or upload is False or isinstance(upload, FieldFile):
        return upload
    maximum = getattr(settings, "MAX_PHOTO_BYTES", 10 * 1024 * 1024)
    if upload.size > maximum:
        raise ValidationError("Фото превышает допустимый размер (10 МБ).")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(upload)
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError("Загрузите фото JPEG, PNG или WebP.")
            if image.width * image.height > getattr(settings, "MAX_PHOTO_PIXELS", 25_000_000):
                raise ValidationError("Слишком большое разрешение фотографии.")
            image.load()
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((2000, 2000))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("Файл не является безопасным изображением.") from exc
    finally:
        upload.seek(0)
    # Re-encoding intentionally discards EXIF and the supplied filename.
    return ContentFile(output.getvalue(), name="photo.jpg")


class WorkspaceModelForm(forms.ModelForm):
    def __init__(self, *args, workspace, **kwargs):
        self.workspace = workspace
        super().__init__(*args, **kwargs)
        self.instance.workspace = workspace
        for field in self.fields.values():
            if isinstance(field, forms.ModelChoiceField) and hasattr(field.queryset.model, "workspace"):
                field.queryset = field.queryset.filter(workspace=workspace)


class ItemForm(WorkspaceModelForm):
    expected_version = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Item
        fields = ["name", "description", "photo", "category", "location", "container", "purchase_date", "price"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "purchase_date": forms.DateInput(attrs={"type": "date"}), "photo": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "capture": "environment"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expected_version"].initial = self.instance.version if self.instance.pk else 0

    def clean_photo(self):
        return clean_photo(self.cleaned_data.get("photo"))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("location") and cleaned.get("container"):
            raise ValidationError("Выберите место или коробку, а не оба варианта одновременно.")
        if self.instance.pk and cleaned.get("expected_version") is None:
            self.add_error("expected_version", "Обновите страницу перед сохранением.")
        return cleaned


class ContainerForm(WorkspaceModelForm):
    expected_version = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Container
        fields = ["name", "description", "location"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expected_version"].initial = self.instance.version if self.instance.pk else 0


    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and cleaned.get("expected_version") is None:
            self.add_error("expected_version", "Обновите страницу перед сохранением.")
        return cleaned


class LocationForm(WorkspaceModelForm):
    class Meta:
        model = Location
        fields = ["name", "description", "parent"]


class CategoryForm(WorkspaceModelForm):
    class Meta:
        model = Category
        fields = ["name", "icon"]


class FilterForm(forms.Form):
    q = forms.CharField(label="Поиск", max_length=200, required=False)
    category = forms.ModelChoiceField(label="Категория", queryset=Category.objects.none(), required=False)
    location = forms.ModelChoiceField(label="Место", queryset=Location.objects.none(), required=False)
    container = forms.ModelChoiceField(label="Коробка", queryset=Container.objects.none(), required=False)

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("category", "location", "container"):
            model = {"category": Category, "location": Location, "container": Container}[name]
            self.fields[name].queryset = model.objects.filter(workspace=workspace) if workspace else model.objects.none()


class ContainerMoveForm(forms.Form):
    location = forms.ModelChoiceField(label="Новое место", queryset=Location.objects.none(), required=False)
    expected_version = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, container, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = Location.objects.filter(workspace=container.workspace)
        self.fields["location"].initial = container.location_id
        self.fields["expected_version"].initial = container.version


class LoanForm(forms.Form):
    borrower = forms.ModelChoiceField(label="Кому выдать", queryset=get_user_model().objects.none())
    due_date = forms.DateField(label="Вернуть до", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, workspace, **kwargs):
        from workspaces.models import Membership
        super().__init__(*args, **kwargs)
        ids = Membership.objects.filter(workspace=workspace).values_list("user_id", flat=True)
        self.fields["borrower"].queryset = get_user_model().objects.filter(pk__in=ids, is_active=True)


class ListingForm(forms.ModelForm):
    class Meta:
        model = PublicListing
        fields = ["title", "description", "active"]
        labels = {"title": "Публичное название", "description": "Публичное описание", "active": "Разрешить просмотр по публичной ссылке"}
        help_texts = {"description": "Не указывайте адрес, контакты и личные заметки. Публикуются только эти название и описание."}
