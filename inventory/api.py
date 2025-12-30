from ninja import Router, Schema
from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.db import models  # Правильный импорт

from inventory.models import Item
from categories.models import Category
from locations.models import Location

router = Router()


# Схемы (остаются без изменений)
class ItemSchema(Schema):
    id: int
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    price: Optional[float] = None
    photo_url: Optional[str] = None
    qr_code_url: Optional[str] = None


class ItemCreateSchema(Schema):
    name: str
    description: str = ""
    category_id: Optional[int] = None
    location_id: Optional[int] = None
    price: Optional[float] = None


# Поиск
@router.get("/search", response=List[ItemSchema])
def search_items(request, q: str = ""):
    items = Item.objects.filter(
        models.Q(name__icontains=q) | models.Q(description__icontains=q)
    )[:20]

    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "category": item.category.name if item.category else None,
            "location": item.location.name if item.location else None,
            "price": float(item.price) if item.price else None,
            "photo_url": item.photo.url if item.photo else None,
            "qr_code_url": item.qr_code.url if item.qr_code else None,
        }
        for item in items
    ]


# Получить по ID
@router.get("{item_id}", response=ItemSchema)
def get_item(request, item_id: int):
    item = get_object_or_404(Item, id=item_id)
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.category.name if item.category else None,
        "location": item.location.name if item.location else None,
        "price": float(item.price) if item.price else None,
        "photo_url": item.photo.url if item.photo else None,
        "qr_code_url": item.qr_code.url if item.qr_code else None,
    }


# Создать вещь
@router.post("/", response=ItemSchema)
def create_item(request, data: ItemCreateSchema):
    category = Category.objects.filter(id=data.category_id).first() if data.category_id else None
    location = Location.objects.filter(id=data.location_id).first() if data.location_id else None

    item = Item.objects.create(
        name=data.name,
        description=data.description,
        category=category,
        location=location,
        price=data.price,
    )

    item.generate_qr_code()
    item.save(update_fields=['qr_code'])

    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.category.name if item.category else None,
        "location": item.location.name if item.location else None,
        "price": float(item.price) if item.price else None,
        "photo_url": None,
        "qr_code_url": item.qr_code.url,
    }


# Статистика
@router.get("/stats")
def get_stats(request):
    return {
        "total_items": Item.objects.count(),
        "total_value": Item.objects.aggregate(total=models.Sum('price'))['total'] or 0,
        "categories_count": Category.objects.count(),
        "locations_count": Location.objects.count(),
    }