import os
import sys
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# 1. Загружаем переменные окружения
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Безопасность
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# 3. Хосты и домены
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '.railway.app']
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '')
if allowed_hosts_env:
    ALLOWED_HOSTS.extend(host.strip() for host in allowed_hosts_env.split(',') if host.strip())

CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://homeinventory-production-8d91.up.railway.app'
]

# 4. Application definition
INSTALLED_APPS = [
    "unfold",  # Должен быть выше admin
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Твои приложения
    "inventory.apps.InventoryConfig",
    "locations.apps.LocationsConfig",
    "categories.apps.CategoriesConfig",
    
    "django_extensions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Сразу после Security
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# 5. Debug Toolbar (только локально)
IS_RAILWAY = 'RAILWAY_ENVIRONMENT' in os.environ or 'DATABASE_URL' in os.environ
if DEBUG and not IS_RAILWAY:
    try:
        import debug_toolbar
        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        INTERNAL_IPS = ["127.0.0.1"]
    except ImportError:
        pass

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# 6. Database (Исправлено для устранения 499)
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=0,          # Устраняет зависшие сессии на Railway
            conn_health_checks=True, # Проверяет соединение перед запросом
            ssl_require=False        # Railway проксирует SSL сам
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# 7. Static & Media
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Упрощенный сторедж для стабильности
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# 8. Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# 9. Кэш (DummyCache для избежания ошибок подключения)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# 10. Security (Production)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# 11. Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# 12. Подавление системных проверок
SILENCED_SYSTEM_CHECKS = [
    "security.W004", "security.W008", "security.W012", "security.W016",
    "django_ratelimit.E003", "django_ratelimit.W001"
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Unfold UI
UNFOLD = {
    "SITE_TITLE": "Домашний инвентарь",
    "SITE_HEADER": "Учёт вещей",
}
