# Multi-stage build для HomeInventory
# Этап 1: Сборка зависимостей
FROM python:3.11-slim as builder

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    tcl-dev \
    tk-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем временный SECRET_KEY для сборки статики
ARG SECRET_KEY=dummy_build_secret_key
ENV SECRET_KEY=${SECRET_KEY}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Копируем и устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем необходимые директории
RUN mkdir -p /app/static /app/media /app/logs

# Собираем статику с временным SECRET_KEY
RUN python manage.py collectstatic --noinput

# Создаем пользователя для приложения
RUN useradd -m -u 1001 homeinventory && \
    chown -R homeinventory:homeinventory /app

USER homeinventory

# Этап 2: Финальный образ
FROM python:3.11-slim

# Мета информация
LABEL maintainer="your-email@example.com"
LABEL version="1.0"
LABEL description="HomeInventory Django Application"

# Устанавливаем только runtime зависимости
RUN apt-get update && apt-get install -y \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    libfreetype6 \
    liblcms2-2 \
    libopenjp2-7 \
    libtiff5 \
    libwebp7 \
    libwebpdemux2 \
    libwebpmux3 \
    curl \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/home/homeinventory/.local/bin:${PATH}"

WORKDIR /app

# Копируем Python пакеты из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем приложение из builder
COPY --from=builder /app /app

# Создаем пользователя (такой же UID, как в builder)
RUN useradd -m -u 1001 homeinventory && \
    chown -R homeinventory:homeinventory /app

USER homeinventory

# Проверяем, что зависимости установлены
RUN python -c "import django; print(f'Django version: {django.__version__}')" && \
    python -c "import psycopg2; print(f'Psycopg2 version: {psycopg2.__version__}')" && \
    python -c "import whitenoise; print('Whitenoise installed')"

# Создаем health check endpoint
RUN echo 'from django.http import JsonResponse\nfrom django.views.decorators.http import require_GET\n@require_GET\ndef health_check(request):\n    return JsonResponse({"status": "healthy", "service": "homeinventory"})' > /app/health.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health/ || exit 1

# Команда запуска
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile - config.wsgi:application"]