# 📦 HomeInventory

**Домашний инвентарь с QR-кодами** — современное Django-приложение для учёта вещей в квартире, офисе или складе. Сканируйте коробки телефоном и мгновенно находите содержимое!

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

## ✨ Преимущества

| Фича | Как это помогает |
|------|------------------|
| **📱 QR-коды** | Приклейте на коробку → сканируйте телефоном → сразу видите содержимое |
| **🔍 Мгновенный поиск** | Найдите "паспорт" за 2 секунды, не перебирая 50 коробок |
| **📊 Статистика** | Знаете общую стоимость вещей и сколько категорий |
| **📤 Экспорт в CSV** | Для страховки или переезда — скачайте весь список за 1 клик |
| **🔒 Защита** | Rate limiting, секретная админка, 2FA (опционально) |
| **🎨 Современный UI** | Django Unfold — админка, как в 2025 году |

## 🚀 Быстрый старт

### Требования
- Python 3.10+
- SQLite (по умолчанию) или PostgreSQL

### Установка (5 минут)

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/yourusername/homeinventory.git
cd homeinventory

# 2. Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Создайте .env файл (скопируйте .env.example)
cp .env.example .env
# Отредактируйте .env, вставьте SECRET_KEY

# 5. Запустите миграции
python manage.py migrate

# 6. Создайте суперпользователя
python manage.py createsuperuser

screenshots/home.png
screenshots/admin.png
screenshots/admin1.png
screenshots/qr.png


# 7. Запустите сервер
python manage.py runserver 0.0.0.0:8000
