from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.db.migrations.executor import MigrationExecutor
from django.db import connection

from categories.models import Category
from locations.models import Location
from workspaces.models import Membership, Workspace
from inventory.models import Container, Item, Loan, Movement, PublicListing
from inventory.services import checkout_item, move_container, move_item, return_loan


class DomainTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('owner', is_staff=True)
        cls.viewer = get_user_model().objects.create_user('viewer', is_staff=True)
        cls.space = Workspace.objects.create(name='Дом')
        cls.other = Workspace.objects.create(name='Мастерская', kind='workshop')
        Membership.objects.create(user=cls.user, workspace=cls.space, role='owner')
        Membership.objects.create(user=cls.viewer, workspace=cls.space, role='viewer')
        cls.room = Location.objects.create(workspace=cls.space, name='Комната')
        cls.new_room = Location.objects.create(workspace=cls.space, name='Кладовка')
        cls.foreign_room = Location.objects.create(workspace=cls.other, name='Чужой склад')
        cls.category = Category.objects.create(workspace=cls.space, name='Документы')
        cls.box = Container.objects.create(workspace=cls.space, name='Коробка', location=cls.room)
        cls.item = Item.objects.create(workspace=cls.space, name='Паспорт', container=cls.box)

    def test_save_has_no_qr_file_side_effect(self):
        self.assertFalse(self.item.qr_code)
        self.assertTrue(self.item.label_id)

    def test_search_text_casefolds_unicode(self):
        self.assertIn('паспорт', self.item.search_text)
        self.assertTrue(Item.objects.filter(search_text__contains='паспорт').exists())

    def test_bulk_import_missing_qr_is_valid_model_state(self):
        imported = Item(workspace=self.space, name='Импорт')
        Item.objects.bulk_create([imported])
        self.assertFalse(Item.objects.get(pk=imported.pk).qr_code)

    def test_cross_workspace_category_rejected(self):
        category = Category.objects.create(workspace=self.other, name='Чужое')
        self.item.category = category
        with self.assertRaises(ValidationError):
            self.item.save()

    def test_cross_workspace_container_rejected(self):
        box = Container.objects.create(workspace=self.other, name='Чужая коробка')
        self.item.container = box
        with self.assertRaises(ValidationError):
            self.item.save()

    def test_workspace_cannot_be_reassigned(self):
        self.item.workspace = self.other
        self.item.container = None
        with self.assertRaises(ValidationError):
            self.item.save()

    def test_item_has_only_one_place(self):
        self.item.location = self.room
        with self.assertRaises(ValidationError):
            self.item.save()

    def test_location_cycles_and_foreign_parent_rejected(self):
        child = Location.objects.create(workspace=self.space, name='Полка', parent=self.room)
        self.room.parent = child
        with self.assertRaises(ValidationError):
            self.room.save()
        self.room.parent = self.foreign_room
        with self.assertRaises(ValidationError):
            self.room.save()

    def test_moving_box_moves_effective_location_of_all_contents(self):
        moved = move_container(self.box, actor=self.user, location=self.new_room, expected_version=0)
        self.item.refresh_from_db()
        self.assertEqual(self.item.effective_location, self.new_room)
        self.assertEqual(moved.version, 1)
        event = Movement.objects.get(container=moved)
        self.assertEqual(event.from_location, self.room)
        self.assertEqual(event.to_location, self.new_room)
        self.assertEqual(event.actor, self.user)

    def test_stale_move_does_not_overwrite_newer_location(self):
        move_container(self.box, actor=self.user, location=self.new_room, expected_version=0)
        with self.assertRaises(ValidationError):
            move_container(self.box, actor=self.user, location=self.room, expected_version=0)
        self.box.refresh_from_db()
        self.assertEqual(self.box.location, self.new_room)

    def test_move_rejects_cross_workspace_place(self):
        with self.assertRaises(ValidationError):
            move_container(self.box, actor=self.user, location=self.foreign_room, expected_version=0)
        self.box.refresh_from_db()
        self.assertEqual(self.box.location, self.room)
        self.assertFalse(Movement.objects.exists())

    def test_viewer_cannot_move_item(self):
        with self.assertRaises(PermissionDenied):
            move_item(self.item, actor=self.viewer, location=self.new_room)

    def test_move_item_records_origin_and_clears_box(self):
        moved = move_item(self.item, actor=self.user, location=self.new_room, expected_version=0)
        self.assertIsNone(moved.container)
        self.assertEqual(moved.location, self.new_room)
        self.assertEqual(Movement.objects.get(item=moved).from_location, self.room)

    def test_checkout_and_idempotent_return(self):
        loan = checkout_item(self.item, actor=self.user, borrower=self.viewer)
        with self.assertRaises(ValidationError):
            checkout_item(self.item, actor=self.user, borrower=self.viewer)
        returned = return_loan(loan, actor=self.user)
        stamp = returned.returned_at
        self.assertIsNotNone(stamp)
        self.assertEqual(return_loan(returned, actor=self.user).returned_at, stamp)
        self.assertTrue(checkout_item(self.item, actor=self.user, borrower=self.viewer).pk)

    def test_db_blocks_two_active_loans(self):
        checkout_item(self.item, actor=self.user, borrower=self.viewer)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Loan.objects.create(workspace=self.space, item=self.item, borrower=self.viewer, opened_by=self.user)

    def test_borrower_must_be_member_of_same_workspace(self):
        outsider = get_user_model().objects.create_user('outsider')
        with self.assertRaises(ValidationError):
            checkout_item(self.item, actor=self.user, borrower=outsider)

    def test_public_listing_cannot_reference_foreign_item(self):
        with self.assertRaises(ValidationError):
            PublicListing.objects.create(workspace=self.other, item=self.item, title='Публичное')

    def test_staff_viewer_cannot_delete_with_native_delete_permission(self):
        self.viewer.user_permissions.add(Permission.objects.get(codename='delete_item'))
        request = RequestFactory().get('/admin/')
        request.user = self.viewer
        self.assertFalse(admin.site._registry[Item].has_delete_permission(request, self.item))

    def test_owner_without_native_delete_permission_cannot_delete_in_admin(self):
        request = RequestFactory().get('/admin/')
        request.user = self.user
        self.assertFalse(admin.site._registry[Item].has_delete_permission(request, self.item))

    def test_admin_queryset_and_relations_are_scoped(self):
        Item.objects.create(workspace=self.other, name='Чужой предмет')
        request = RequestFactory().get('/admin/')
        request.user = self.user
        registry = admin.site._registry[Item]
        self.assertEqual(list(registry.get_queryset(request)), [self.item])
        field = registry.formfield_for_foreignkey(Item._meta.get_field('location'), request)
        self.assertNotIn(self.foreign_room, field.queryset)

    def test_admin_membership_changes_are_superuser_only(self):
        self.user.user_permissions.add(Permission.objects.get(codename='change_membership'))
        request = RequestFactory().get('/admin/')
        request.user = self.user
        self.assertFalse(admin.site._registry[Membership].has_change_permission(request))


class LegacyMigrationTests(TransactionTestCase):
    """Exercise real historical schema/data migration, including several UUIDs."""
    reset_sequences = True

    def test_existing_inventory_is_preserved_without_granting_access(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [('inventory', '0002_alter_item_category_alter_item_location'), ('categories', '0001_initial'), ('locations', '0001_initial')]
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            category = apps.get_model('categories', 'Category').objects.create(name='Старая категория')
            location = apps.get_model('locations', 'Location').objects.create(name='Старая комната')
            old_item = apps.get_model('inventory', 'Item')
            first = old_item.objects.create(name='Паспорт', category=category, location=location, photo='items/legacy.jpg', qr_code='qrcodes/legacy.png')
            second = old_item.objects.create(name='Второй предмет')
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            item = Item.objects.get(pk=first.pk)
            other = Item.objects.get(pk=second.pk)
            self.assertEqual(item.workspace.name, 'Импортированные данные')
            self.assertEqual(item.category.name, 'Старая категория')
            self.assertEqual(item.location.name, 'Старая комната')
            self.assertEqual(item.photo.name, 'items/legacy.jpg')
            self.assertEqual(item.qr_code.name, 'qrcodes/legacy.png')
            self.assertNotEqual(item.label_id, other.label_id)
            self.assertIn('паспорт', item.search_text)
            self.assertFalse(Membership.objects.filter(workspace=item.workspace).exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
