"""Settings shared by local development and the production deployment.

Development is opt-in (DEBUG=True). A production process must be configured
explicitly rather than silently using a public signing key or hosting origin.
"""
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {'1', 'true', 'yes'}


def env_list(name, default=''):
    return [value.strip() for value in os.environ.get(name, default).split(',') if value.strip()]


DEBUG = env_bool('DEBUG')
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY and DEBUG:
    SECRET_KEY = 'development-only-do-not-deploy-this-signing-key-change-me-1234567890'
if not DEBUG and (len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 8 or SECRET_KEY.startswith(('django-insecure-', 'development-'))):
    raise ImproperlyConfigured('Production requires a random SECRET_KEY of at least 50 characters.')

PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://localhost:8000' if DEBUG else '').rstrip('/')
_public_url = urlsplit(PUBLIC_BASE_URL)
if _public_url.scheme not in {'http', 'https'} or not _public_url.hostname or _public_url.username or _public_url.password or _public_url.path or _public_url.query or _public_url.fragment:
    raise ImproperlyConfigured('PUBLIC_BASE_URL must be an absolute origin without a path or credentials.')
if not DEBUG and _public_url.scheme != 'https':
    raise ImproperlyConfigured('Production PUBLIC_BASE_URL must use HTTPS.')
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else _public_url.hostname)
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', PUBLIC_BASE_URL)
if any(host == '*' or host.startswith('.') or '*' in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('ALLOWED_HOSTS must contain exact hostnames.')
if any('*' in origin for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS must contain exact origins.')

INSTALLED_APPS = [
    'unfold',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'axes',
    'workspaces.apps.WorkspacesConfig',
    'inventory.apps.InventoryConfig',
    'locations.apps.LocationsConfig',
    'categories.apps.CategoriesConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

_database_url = os.environ.get('DATABASE_URL')
if _database_url:
    DATABASES = {'default': dj_database_url.parse(_database_url, conn_max_age=60, conn_health_checks=True)}
    if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
        # libpq performs certificate/hostname verification for external databases.
        # Override only for a known private/local PostgreSQL deployment.
        DATABASES['default'].setdefault('OPTIONS', {})['sslmode'] = os.environ.get('DB_SSLMODE', 'prefer' if DEBUG else 'verify-full')
        if DATABASES['default']['OPTIONS']['sslmode'] in {'verify-ca', 'verify-full'}:
            DATABASES['default']['OPTIONS'].setdefault('sslrootcert', os.environ.get('DB_SSLROOTCERT', '/etc/ssl/certs/ca-certificates.crt'))
else:
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')),
        'OPTIONS': {'timeout': 20},
    }}

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
# Never expose this directory via a public static()/nginx alias.
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'media')))
MEDIA_URL = '/media/'
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTO_PIXELS = 25_000_000
ARCHIVE_MAX_BYTES = 25 * 1024 * 1024
ARCHIVE_MAX_EXPANDED_BYTES = 100 * 1024 * 1024
ARCHIVE_MAX_FILES = 1000

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'
AUTHENTICATION_BACKENDS = ['axes.backends.AxesStandaloneBackend', 'django.contrib.auth.backends.ModelBackend']
# Shared database counters work across workers and survive process restarts.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_RESET_ON_SUCCESS = True
AXES_CLIENT_IP_CALLABLE = 'config.security.client_ip'
AXES_ENABLE_ACCESS_FAILURE_LOG = False
AXES_VERBOSE = False

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
# Enable only when the application is reached exclusively through your TLS proxy.
if env_bool('TRUST_PROXY_HTTPS'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# A loopback/infrastructure health probe has no user data and need not redirect.
SECURE_REDIRECT_EXEMPT = [r'^health/$']

LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {'axes': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False}},
}
UNFOLD = {'SITE_TITLE': 'Домашний инвентарь', 'SITE_HEADER': 'Учёт вещей'}
AXES_HTTP_RESPONSE_CODE = 429
