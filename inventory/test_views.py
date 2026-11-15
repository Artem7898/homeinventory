import io
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from PIL import Image

from categories.models import Category
from locations.models import Location
from workspaces.models import Membership, Workspace
from .forms import clean_photo
from .models import Container, Item, Loan, PublicListing


def photo(name='photo.png'):
    buffer = io.BytesIO()
    image = Image.new('RGB', (40, 30), color='green')
    image.save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class PrivateViewsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory()
        cls.media_settings = override_settings(MEDIA_ROOT=cls.media.name)
        cls.media_settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.media_settings.disable()
        cls.media.cleanup()

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username='owner', password='test-password')
        cls.viewer = User.objects.create_user(username='viewer', password='test-password')
        cls.editor = User.objects.create_user(username='editor', password='test-password')
        cls.outsider = User.objects.create_user(username='outsider', password='test-password')
        cls.workspace = Workspace.objects.create(name='Home')
        cls.other = Workspace.objects.create(name='Other')
        for user, role in [(cls.owner, 'owner'), (cls.viewer, 'viewer'), (cls.editor, 'editor')]:
            Membership.objects.create(workspace=cls.workspace, user=user, role=role)
        Membership.objects.create(workspace=cls.other, user=cls.outsider, role='owner')
        cls.location = Location.objects.create(workspace=cls.workspace, name='Garage')
        cls.other_location = Location.objects.create(workspace=cls.other, name='Private address')
        cls.category = Category.objects.create(workspace=cls.workspace, name='Documents')
        cls.box = Container.objects.create(workspace=cls.workspace, name='Box', location=cls.location)
        cls.item = Item.objects.create(workspace=cls.workspace, name='Паспорт', description='PRIVATE NOTE', category=cls.category, location=cls.location, price='0.00')
        cls.foreign = Item.objects.create(workspace=cls.other, name='FOREIGN SECRET', location=cls.other_location)

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def item_data(self, **extra):
        return {'name': 'Updated', 'description': 'Details', 'category': self.category.pk, 'location': self.location.pk, 'expected_version': self.item.version, **extra}

    def test_all_private_views_require_login(self):
        routes = ['/', '/export/', '/scanner/', '/labels/', '/containers/', '/api/', f'/api/items/{self.item.pk}/', self.item.get_absolute_url(), f'/item/{self.item.pk}/qr.png', self.item.get_label_url(), '/media/items/not-found.jpg']
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/accounts/login/', response.url)

    def test_membership_limits_lists_exports_and_object_lookups(self):
        self.login()
        self.assertContains(self.client.get('/'), 'Паспорт')
        self.assertNotContains(self.client.get('/'), 'FOREIGN SECRET')
        self.assertNotContains(self.client.get('/export/'), 'FOREIGN SECRET')
        for path in [self.foreign.get_absolute_url(), self.foreign.get_label_url(), f'/api/items/{self.foreign.pk}/', f'/item/{self.foreign.pk}/qr.png']:
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_forged_active_workspace_cannot_bypass_membership(self):
        self.login()
        session = self.client.session
        session['workspace_id'] = self.other.pk
        session.save()
        self.assertNotContains(self.client.get('/'), 'FOREIGN SECRET')
        self.assertEqual(self.client.post(reverse('workspaces:workspace-select', args=[self.other.pk])).status_code, 404)

    def test_viewer_reads_but_cannot_write(self):
        self.login(self.viewer)
        self.assertEqual(self.client.get(self.item.get_absolute_url()).status_code, 200)
        for route in [reverse('inventory:item-create'), reverse('inventory:item-edit', args=[self.item.pk]), reverse('inventory:item-delete', args=[self.item.pk]), reverse('inventory:container-create'), reverse('inventory:category-create'), reverse('inventory:location-create')]:
            with self.subTest(route=route):
                self.assertEqual(self.client.post(route, self.item_data()).status_code, 403)
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())

    def test_cross_workspace_foreign_key_is_rejected(self):
        self.login(self.editor)
        response = self.client.post(reverse('inventory:item-create'), self.item_data(location=self.other_location.pk))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Item.objects.filter(name='Updated').exists())

    def test_unicode_search_is_case_insensitive(self):
        self.login()
        for query in ['паспорт', 'ПАСПОРТ', 'Паспорт']:
            self.assertContains(self.client.get('/search/', {'q': query}), 'Паспорт')

    def test_invalid_filter_is_400_not_500(self):
        self.login()
        for key in ['category', 'location', 'container']:
            self.assertEqual(self.client.get('/', {key: 'not-an-id'}).status_code, 400)
            self.assertEqual(self.client.get('/', {key: self.other_location.pk}).status_code, 400 if key == 'location' else 400)

    def test_zero_price_is_displayed(self):
        self.login()
        self.assertContains(self.client.get(self.item.get_absolute_url()), '0')

    def test_item_without_stored_qr_renders_and_generates_on_demand(self):
        self.login()
        self.assertFalse(self.item.qr_code)
        self.assertEqual(self.client.get(self.item.get_absolute_url()).status_code, 200)
        with override_settings(PUBLIC_BASE_URL='https://inventory.example'):
            import qrcode
            with patch('inventory.views.qrcode.make', wraps=qrcode.make) as make:
                response = self.client.get(reverse('inventory:item-qr', args=[self.item.pk]))
                self.assertEqual(make.call_args.args[0], 'https://inventory.example' + self.item.get_label_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        with Image.open(io.BytesIO(response.content)) as image:
            self.assertEqual(image.format, 'PNG')
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_label_and_short_code_resolve_to_authorized_item(self):
        self.login()
        self.assertRedirects(self.client.get(self.item.get_label_url()), self.item.get_absolute_url())
        self.assertRedirects(self.client.post(reverse('inventory:label-resolve'), {'kind': 'item', 'code': str(self.item.label_id)[:8]}), self.item.get_absolute_url())
        self.assertEqual(self.client.post(reverse('inventory:label-resolve'), {'kind': 'item', 'code': str(self.foreign.label_id)[:8]}).status_code, 400)
        self.assertEqual(self.client.post(reverse('inventory:label-resolve'), {'kind': 'item', 'code': '<script>'}).status_code, 400)

    def test_api_contract_is_private_and_works(self):
        self.login()
        self.assertEqual(self.client.get('/api/').status_code, 200)
        data = self.client.get(f'/api/items/{self.item.pk}/').json()
        self.assertEqual(data['name'], 'Паспорт')
        self.assertNotIn('description', data)
        self.assertNotIn('price', data)

    def test_export_neutralizes_formula_cells(self):
        self.login()
        Item.objects.create(workspace=self.workspace, name='=1+1', description=' \t@SUM(1)')
        result = self.client.get('/export/').content.decode('utf-8-sig')
        self.assertIn("'=1+1", result)
        self.assertIn("' \t@SUM(1)", result)
        self.assertIn('0.00', result)

    def test_pagination_and_query_count_are_bounded(self):
        self.login()
        Item.objects.bulk_create([Item(workspace=self.workspace, name=f'Part {i}', category=self.category, location=self.location) for i in range(55)])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/')
        self.assertEqual(len(response.context['page_obj'].object_list), 24)
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertLess(len(queries), 20, f'{len(queries)} SQL queries')

    def test_edits_detect_conflicts_without_overwriting(self):
        self.login(self.editor)
        url = reverse('inventory:item-edit', args=[self.item.pk])
        self.assertEqual(self.client.post(url, self.item_data(name='First')).status_code, 302)
        self.assertEqual(self.client.post(url, self.item_data(name='Stale')).status_code, 400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, 'First')
        self.assertGreater(self.item.version, 0)

    def test_container_edit_requires_current_version(self):
        self.login(self.editor)
        url = reverse('inventory:container-edit', args=[self.box.pk])
        self.assertEqual(self.client.post(url, {'name': 'Missing token', 'location': self.location.pk}).status_code, 400)
        self.box.refresh_from_db()
        self.assertEqual(self.box.name, 'Box')
        self.assertEqual(self.client.post(url, {'name': 'Updated box', 'location': self.location.pk, 'expected_version': self.box.version}).status_code, 302)
        self.assertEqual(self.client.post(url, {'name': 'Stale box', 'location': self.location.pk, 'expected_version': self.box.version}).status_code, 400)
        self.box.refresh_from_db()
        self.assertEqual(self.box.name, 'Updated box')

    def test_container_move_updates_content_location_and_history(self):
        self.login(self.editor)
        item = Item.objects.create(workspace=self.workspace, name='Inside box', container=self.box)
        destination = Location.objects.create(workspace=self.workspace, name='Storage room')
        response = self.client.post(reverse('inventory:container-move', args=[self.box.pk]), {'location': destination.pk, 'expected_version': self.box.version})
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.effective_location, destination)
        self.assertEqual(self.box.movements.count(), 1)

    def test_valid_photo_upload_is_reencoded_and_saved_privately(self):
        self.login(self.editor)
        response = self.client.post(reverse('inventory:item-create'), self.item_data(name='Uploaded photograph', photo=photo()))
        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name='Uploaded photograph')
        self.assertTrue(item.photo.name.endswith('.jpg'))
        with Image.open(item.photo.path) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertFalse(image.getexif())
        response = self.client.get(item.photo.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content))

    def test_photo_is_private_even_with_debug_false(self):
        self.item.photo.save('private.png', ContentFile(photo().read()), save=True)
        self.login()
        response = self.client.get(self.item.photo.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertTrue(b''.join(response.streaming_content))
        self.login(self.outsider)
        self.assertEqual(self.client.get(self.item.photo.url).status_code, 404)
        self.assertEqual(self.client.get('/media/../db.sqlite3').status_code, 404)

    def test_invalid_photo_is_rejected(self):
        self.login()
        response = self.client.post(reverse('inventory:item-create'), self.item_data(photo=SimpleUploadedFile('evil.png', b'not an image', content_type='image/png')))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Item.objects.filter(name='Updated').exists())

    def test_photo_reencoding_strips_metadata_and_limits_size(self):
        image = Image.new('RGB', (40, 30))
        exif = Image.Exif()
        exif[270] = 'private metadata'
        output = io.BytesIO()
        image.save(output, format='JPEG', exif=exif)
        clean = clean_photo(ContentFile(output.getvalue(), name='source.jpg'))
        with Image.open(clean) as image:
            self.assertFalse(image.getexif())
        with override_settings(MAX_PHOTO_BYTES=1):
            from django.core.exceptions import ValidationError
            with self.assertRaises(ValidationError):
                clean_photo(photo())

    def test_public_listing_contains_only_explicit_fields_and_can_be_revoked(self):
        listing = PublicListing.objects.create(workspace=self.workspace, item=self.item, title='Shared drill', description='Public summary', active=True)
        response = self.client.get(listing.get_absolute_url())
        self.assertContains(response, 'Shared drill')
        self.assertNotContains(response, 'PRIVATE NOTE')
        self.assertNotContains(response, 'Garage')
        self.assertNotContains(response, 'Паспорт')
        self.assertEqual(response['Cache-Control'], 'no-store')
        listing.active = False
        listing.save()
        self.assertEqual(self.client.get(listing.get_absolute_url()).status_code, 404)

    def test_only_owner_manages_publication(self):
        self.login(self.editor)
        self.assertEqual(self.client.post(reverse('inventory:listing-edit', args=[self.item.pk]), {'title': 'Public', 'description': 'test', 'active': 'on'}).status_code, 403)
        self.assertFalse(PublicListing.objects.exists())

    def test_loan_cycle_and_wrong_workspace_borrower(self):
        self.login(self.editor)
        url = reverse('inventory:loan-checkout', args=[self.item.pk])
        self.assertEqual(self.client.post(url, {'borrower': self.outsider.pk}).status_code, 400)
        self.assertEqual(self.client.post(url, {'borrower': self.viewer.pk}).status_code, 302)
        loan = Loan.objects.get(item=self.item)
        self.assertEqual(self.client.post(url, {'borrower': self.viewer.pk}).status_code, 400)
        return_url = reverse('inventory:loan-return', args=[loan.pk])
        self.assertEqual(self.client.post(return_url).status_code, 302)
        self.assertEqual(self.client.post(return_url).status_code, 302)
        loan.refresh_from_db()
        self.assertIsNotNone(loan.returned_at)

    def test_csrf_and_post_only_mutations(self):
        self.login()
        self.assertEqual(self.client.get(reverse('inventory:item-delete', args=[self.item.pk])).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('inventory:item-delete', args=[self.item.pk])).status_code, 403)
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())

    def test_health_public_and_minimal(self):
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
