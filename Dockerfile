FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . .

# Сборка статики
RUN python manage.py collectstatic --noinput

# Порт
EXPOSE 8000

# Команда запуска
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 3 config.wsgi:application
