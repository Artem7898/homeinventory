from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Item
from categories.models import Category
from locations.models import Location
import csv
from django.http import HttpResponse


def item_list(request):
    """Главная страница со списком вещей и поиском"""
    items = Item.objects.all()

    # Поиск
    query = request.GET.get('q')
    if query:
        items = items.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    # Фильтры
    category_id = request.GET.get('category')
    location_id = request.GET.get('location')

    if category_id:
        items = items.filter(category_id=category_id)
    if location_id:
        items = items.filter(location_id=location_id)

    categories = Category.objects.all()
    locations = Location.objects.all()

    context = {
        'items': items,
        'categories': categories,
        'locations': locations,
        'query': query,
    }
    return render(request, 'inventory/item_list.html', context)


def item_detail(request, pk):
    """Страница одной вещи с QR-кодом"""
    item = get_object_or_404(Item, pk=pk)
    return render(request, 'inventory/item_detail.html', {'item': item})


def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory.csv"'

    writer = csv.writer(response)
    writer.writerow(['Название', 'Категория', 'Место', 'Цена'])

    for item in Item.objects.all():
        writer.writerow([
            item.name,
            item.category.name if item.category else '-',
            item.location.name if item.location else '-',
            item.price or 0
        ])

    return response


def search_view(request):
    """Отдельная страница поиска"""
    query = request.GET.get('q', '')
    items = Item.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query)
    ) if query else []

    return render(request, 'inventory/search.html', {
        'items': items,
        'query': query,
    })


def scanner_view(request):
    return render(request, 'inventory/scanner.html')


# Обработчики ошибок
def page_not_found(request, exception):
    """Страница 404 - не найдено"""
    return render(request, 'inventory/error.html', {
        'error_code': '404',
        'error_title': 'Страница не найдена',
        'error_message': 'Извините, запрашиваемая страница не существует.',
        'error_details': 'Проверьте правильность URL или вернитесь на главную страницу.'
    }, status=404)


def server_error(request):
    """Страница 500 - внутренняя ошибка сервера"""
    return render(request, 'inventory/error.html', {
        'error_code': '500',
        'error_title': 'Внутренняя ошибка сервера',
        'error_message': 'Произошла внутренняя ошибка сервера.',
        'error_details': 'Попробуйте обновить страницу или вернуться позже.'
    }, status=500)


def bad_request(request, exception):
    """Страница 400 - неверный запрос"""
    return render(request, 'inventory/error.html', {
        'error_code': '400',
        'error_title': 'Неверный запрос',
        'error_message': 'Запрос не может быть обработан сервером.',
        'error_details': 'Проверьте правильность введенных данных.'
    }, status=400)


def permission_denied(request, exception):
    """Страница 403 - доступ запрещен"""
    return render(request, 'inventory/error.html', {
        'error_code': '403',
        'error_title': 'Доступ запрещен',
        'error_message': 'У вас нет прав для доступа к этой странице.',
        'error_details': 'Обратитесь к администратору для получения доступа.'
    }, status=403)
