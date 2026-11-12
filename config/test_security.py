import os
import subprocess
import sys
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


class ProductionSettingsTests(SimpleTestCase):
    def import_settings(self, **overrides):
        env = {key: value for key, value in os.environ.items() if key not in {
            'DJANGO_SETTINGS_MODULE', 'DATABASE_URL', 'DEBUG', 'SECRET_KEY',
            'PUBLIC_BASE_URL', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS',
        }}
        env.update(DEBUG='False', SECRET_KEY='test-only-production-config-key-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                   PUBLIC_BASE_URL='https://inventory.example.org')
        env.update(overrides)
        return subprocess.run([sys.executable, '-c', 'import config.settings'], env=env,
                              cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)

    def test_production_rejects_missing_secret(self):
        self.assertNotEqual(self.import_settings(SECRET_KEY='').returncode, 0)

    def test_production_rejects_public_development_key(self):
        self.assertNotEqual(self.import_settings(SECRET_KEY='development-only-do-not-deploy-this-signing-key-change-me-1234567890').returncode, 0)

    def test_production_rejects_insecure_origin(self):
        self.assertNotEqual(self.import_settings(PUBLIC_BASE_URL='http://inventory.example.org').returncode, 0)

    def test_production_rejects_wildcard_hosts(self):
        self.assertNotEqual(self.import_settings(ALLOWED_HOSTS='.railway.app').returncode, 0)

    def test_production_rejects_wildcard_csrf_origin(self):
        self.assertNotEqual(self.import_settings(CSRF_TRUSTED_ORIGINS='https://*.railway.app').returncode, 0)

    def test_valid_exact_production_config_loads(self):
        result = self.import_settings()
        self.assertEqual(result.returncode, 0, result.stderr)


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
class LoginThrottleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('throttle-user', password='correct-test-password')

    def test_failed_login_locks_correct_password_too(self):
        for _ in range(3):
            self.client.post(reverse('login'), {'username': self.user.username, 'password': 'wrong'})
        response = self.client.post(reverse('login'), {'username': self.user.username, 'password': 'correct-test-password'})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_forwarded_ip_cannot_bypass_lockout(self):
        for i in range(3):
            self.client.post(reverse('login'), {'username': self.user.username, 'password': 'wrong'},
                             HTTP_X_FORWARDED_FOR=f'192.0.2.{i}')
        response = self.client.post(reverse('login'), {'username': self.user.username, 'password': 'correct-test-password'},
                                    HTTP_X_FORWARDED_FOR='192.0.2.99')
        self.assertEqual(response.status_code, 429)
