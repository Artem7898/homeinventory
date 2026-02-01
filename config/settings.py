"""
Django settings for config project.
"""

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Базовые настройки
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Настройки административной панели
ADMIN_URL = os.environ.get('ADMIN_URL', 'admin')  # ← ДОБАВЛЕНО

# Определяем, работаем ли на Railway
IS_RAILWAY = 'RAILWAY_ENVIRONMENT' in os.environ or 'DATABASE_URL' in os.environ

# Настройки ALLOWED_HOSTS
ALLOWED_HOSTS = []
if DEBUG:
    ALLOWED_HOSTS.extend(['localhost', '127.0.0.1', '0.0.0.0'])
else:
    # Для production получаем hosts из переменной окружения
    allowed_hosts = os.environ.get('ALLOWED_HOSTS', '')
    if allowed_hosts:
        ALLOWED_HOSTS.extend(host.strip() for host in allowed_hosts.split(',') if host.strip())
    
    # Добавляем Railway домены
    ALLOWED_HOSTS.extend(['.railway.app', 'homeinventory-production-8d91.up.railway.app'])

# CSRF и CORS настройки
CSRF_TRUSTED_ORIGINS = []
if not DEBUG:
    CSRF_TRUSTED_ORIGINS.extend([
        'https://*.railway.app',
        'https://homeinventory-production-8d91.up.railway.app',
    ])

# Application definition
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Собственные приложения
    "inventory.apps.InventoryConfig",
    "locations.apps.LocationsConfig",
    "categories.apps.CategoriesConfig",
    
    # Внешние пакеты
    "django_extensions",
    # "django_ratelimit",  # ← ВРЕМЕННО ЗАКОММЕНТИРУЙТЕ ДЛЯ RAILWAY
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Должен быть сразу после SecurityMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Добавляем debug_toolbar только при локальной разработке
if DEBUG and not IS_RAILWAY:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    INTERNAL_IPS = ["127.0.0.1"]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Database
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=not DEBUG,  # SSL только в production
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / 'templates'],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Unfold admin
UNFOLD = {
    "SITE_TITLE": "Домашний инвентарь",
    "SITE_HEADER": "Учёт вещей",
}

# Cache - для Railway используем простой кэш
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',  # ← ИЗМЕНИТЕ НА DummyCache
    }
}

# Security settings - ВАЖНО: только для production
if not DEBUG:  # Только когда DEBUG=False
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # SECURE_SSL_REDIRECT = True  # ← ЗАКОММЕНТИРУЙТЕ ДЛЯ RAILWAY (Railway сам делает SSL)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Подавляем предупреждения
SILENCED_SYSTEM_CHECKS = [
    "security.W004",  # SECURE_HSTS_SECONDS
    "security.W008",  # SECURE_SSL_REDIRECT
    "security.W012",  # SESSION_COOKIE_SECURE
    "security.W016",  # CSRF_COOKIE_SECURE
    "django_ratelimit.E003",  # ← ДОБАВЬТЕ
    "django_ratelimit.W001",  # ← ДОБАВЬТЕ
]
