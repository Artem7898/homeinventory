"""
Django settings for config project.
"""

from pathlib import Path
from decouple import config
import os
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Берем все значения из .env
SECRET_KEY = config('SECRET_KEY', default=os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'))
DEBUG = config('DEBUG', default=False, cast=bool)
ADMIN_URL = config('ADMIN_URL', default='admin')

# Получаем переменные окружения Railway
RAILWAY_ENVIRONMENT = os.environ.get('RAILWAY_ENVIRONMENT', '')
RAILWAY_GIT_BRANCH = os.environ.get('RAILWAY_GIT_BRANCH', '')
IS_RAILWAY = RAILWAY_ENVIRONMENT != ''

# Если мы на Railway, используем их настройки
if IS_RAILWAY:
    DEBUG = False
    ALLOWED_HOSTS = [
        'localhost',
        '127.0.0.1',
        '.railway.app',  # Все домены Railway
        os.environ.get('RAILWAY_PUBLIC_DOMAIN', ''),
        os.environ.get('RAILWAY_PRIVATE_DOMAIN', ''),
    ]
    CSRF_TRUSTED_ORIGINS = [
        'https://*.railway.app',
        f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')}",
        f"https://{os.environ.get('RAILWAY_PRIVATE_DOMAIN', '')}",
    ]
else:
    # Настройки для локальной разработки
    if DEBUG:
        ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '[::1]']
        CSRF_TRUSTED_ORIGINS = [
            'http://localhost:8000',
            'http://127.0.0.1:8000',
            'http://0.0.0.0:8000',
            'homeinventory-production-8d91.up.railway.app',
        ]
    else:
        ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

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
    "whitenoise.runserver_nostatic",  # ← Добавьте для статики на Railway
    # Собственные приложения
    "inventory.apps.InventoryConfig",
    "locations.apps.LocationsConfig",
    "categories.apps.CategoriesConfig",
    # Внешние пакеты
    "django_extensions",
    "django_ratelimit",
]

# Только для локальной разработки добавляем debug_toolbar
if DEBUG and not IS_RAILWAY:
    INSTALLED_APPS.append("debug_toolbar")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # ← Добавьте для статики
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Только для разработки добавляем debug_toolbar
if DEBUG and not IS_RAILWAY:
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

# ===== НАСТРОЙКИ БАЗЫ ДАННЫХ =====
# Используем DATABASE_URL от Railway или из .env
DATABASE_URL = os.environ.get('DATABASE_URL', config('DATABASE_URL', default=''))

if DATABASE_URL:
    # Используем PostgreSQL из DATABASE_URL (Railway)
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Локальная разработка
    USE_POSTGRESQL = config('USE_POSTGRESQL', default=False, cast=bool)
    
    if USE_POSTGRESQL:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": config('DB_NAME', default='homeinventory'),
                "USER": config('DB_USER', default='homeuser'),
                "PASSWORD": config('DB_PASSWORD', default=''),
                "HOST": config('DB_HOST', default='localhost'),
                "PORT": config('DB_PORT', default='5432'),
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }

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
LANGUAGE_CODE = config('LANGUAGE_CODE', default='ru-ru')
TIME_ZONE = config('TIME_ZONE', default='Europe/Moscow')
USE_I18N = True
USE_TZ = True

# Static files (Railway)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# For QR codes
QR_CODE_CACHE_ENABLED = False

# Debug toolbar (только для локальной разработки)
INTERNAL_IPS = ['127.0.0.1'] if DEBUG and not IS_RAILWAY else []

# Unfold admin panel
UNFOLD = {
    "SITE_TITLE": config('SITE_TITLE', default="Домашний инвентарь"),
    "SITE_HEADER": config('SITE_HEADER', default="Учёт вещей"),
    "SITE_URL": "/",
}

# Cache - используем DatabaseCache с созданием таблицы
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'my_cache_table',
    }
}

# Rate limiting - отключаем проверки для DatabaseCache
RATELIMIT_SKIP_CHECK = True

# Подавляем все системные проверки
SILENCED_SYSTEM_CHECKS = [
    "django_ratelimit.E003", 
    "django_ratelimit.W001",
    "debug_toolbar.W001",
]

# Security settings for production
if not DEBUG or IS_RAILWAY:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Логирование для Railway
if IS_RAILWAY:
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
