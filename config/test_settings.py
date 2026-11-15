"""Deterministic test configuration, with production guards exercised separately."""
import os

os.environ['DEBUG'] = 'True'
os.environ.setdefault('PUBLIC_BASE_URL', 'http://localhost:8000')
from .settings import *  # noqa: F403,E402

DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
AXES_ENABLED = False
