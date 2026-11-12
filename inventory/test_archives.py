import io
import json
import sqlite3
import tempfile
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from PIL import Image

from categories.models import Category
from inventory.archive import export_workspace, import_workspace, inspect_archive
from inventory.models import Container, Item
from locations.models import Location
from workspaces.models import Membership, Workspace


def photo():
    out = io.BytesIO()
    Image.new("RGB", (5, 5), "blue").save(out, "PNG")
    return ContentFile(out.getvalue(), name="fixture.png")


def rewrite(data, mutate, extra=None):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(output, "w") as dst:
        manifest = json.loads(src.read("manifest.json"))
        mutate(manifest)
        for name in src.namelist():
            dst.writestr(name, json.dumps(manifest) if name == "manifest.json" else src.read(name))
        if extra:
            dst.writestr(*extra)
    return output.getvalue()


class ArchivesTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        context = override_settings(MEDIA_ROOT=self.temp.name)
        context.enable()
        self.addCleanup(context.disable)
        self.user = get_user_model().objects.create_user("archivist", password="StrongPass123!")
        self.space = Workspace.objects.create(name="Catalog", kind="home")
        Membership.objects.create(workspace=self.space, user=self.user, role="owner")
        self.category = Category.objects.create(workspace=self.space, name="Tools")
        self.location = Location.objects.create(workspace=self.space, name="Garage")
        self.child = Location.objects.create(workspace=self.space, name="Shelf", parent=self.location)
        self.box = Container.objects.create(workspace=self.space, name="Box", location=self.child)
        self.item = Item.objects.create(
            workspace=self.space,
            name="Дрель",
            category=self.category,
            container=self.box,
            price="0.00",
            description="Private notes",
            photo=photo(),
        )
        self.archive = export_workspace(self.space)

    def test_roundtrip_preserves_catalog_and_new_private_owner(self):
        space, created = import_workspace(self.archive, user=self.user)
        self.assertTrue(created)
        self.assertNotEqual(space.pk, self.space.pk)
        item = Item.objects.get(workspace=space)
        self.assertEqual(item.name, self.item.name)
        self.assertEqual(item.price, self.item.price)
        self.assertEqual(item.container.location.parent.name, "Garage")
        self.assertEqual(item.category.name, "Tools")
        self.assertNotEqual(item.label_id, self.item.label_id)
        with Image.open(item.photo.path) as image:
            self.assertEqual(image.size, (5, 5))
        self.assertEqual(list(space.memberships.values_list("user_id", "role")), [(self.user.pk, "owner")])

    def test_import_is_idempotent_for_user(self):
        a, first = import_workspace(self.archive, user=self.user)
        b, second = import_workspace(self.archive, user=self.user)
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(a.pk, b.pk)

    def test_traversal_rejected(self):
        for path in ["../evil", "/tmp/evil", "photos/../evil", "photos\\evil"]:
            with self.subTest(path=path), self.assertRaises(ValidationError):
                inspect_archive(rewrite(self.archive, lambda m: None, (path, b"evil")))

    def test_duplicate_zip_member_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_archive(rewrite(self.archive, lambda m: None, ("manifest.json", "{}")))

    def test_invalid_reference_rejected_without_writes(self):
        count = Workspace.objects.count()
        with self.assertRaises(ValidationError):
            import_workspace(
                rewrite(self.archive, lambda m: m["items"][0].update(category="foreign")), user=self.user
            )
        self.assertEqual(Workspace.objects.count(), count)

    def test_cycle_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_archive(
                rewrite(self.archive, lambda m: m["locations"][0].update(parent=m["locations"][0]["id"]))
            )

    def test_tampered_photo_checksum_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_archive(rewrite(self.archive, lambda m: m["items"][0]["photo"].update(sha256="0" * 64)))

    def test_invalid_field_types_rejected_before_preview(self):
        for field, value in [
            ("purchase_date", {}),
            ("purchase_date", "not-a-date"),
            ("price", []),
            ("price", "NaN"),
        ]:
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                inspect_archive(rewrite(self.archive, lambda m: m["items"][0].update({field: value})))
        with self.assertRaises(ValidationError):
            inspect_archive(rewrite(self.archive, lambda m: m["categories"][0].update(icon={})))

    def test_unsupported_schema_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_archive(rewrite(self.archive, lambda m: m.update(schema_version=100)))

    def test_transaction_rollback_removes_written_photos(self):
        data = rewrite(
            self.archive, lambda m: m["items"].append({"id": "second", "name": "bad", "price": "invalid"})
        )
        before = set(Path(self.temp.name).rglob("*"))
        with self.assertRaises(ValidationError):
            import_workspace(data, user=self.user)
        self.assertEqual(Workspace.objects.count(), 1)
        self.assertEqual(set(Path(self.temp.name).rglob("*")), before)

    def test_anonymous_archive_denied(self):
        self.assertEqual(self.client.get(reverse("archives:export", args=[self.space.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("archives:import")).status_code, 302)

    def test_foreign_space_and_viewer_cannot_export(self):
        other = get_user_model().objects.create_user("outsider")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("archives:export", args=[self.space.pk])).status_code, 404)
        Membership.objects.create(workspace=self.space, user=other, role="viewer")
        self.assertEqual(self.client.get(reverse("archives:export", args=[self.space.pk])).status_code, 403)

    def test_web_import_requires_preview_and_same_session_confirmation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("archives:import"), {"archive": SimpleUploadedFile("catalog.zip", self.archive)}
        )
        self.assertEqual(response.status_code, 200)
        token = response.context["token"]
        self.assertIsNotNone(response.context["preview"])
        self.assertEqual(Workspace.objects.count(), 1)
        another = self.client_class()
        another.force_login(self.user)
        rejected = another.post(reverse("archives:import"), {"action": "confirm", "token": token})
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(Workspace.objects.count(), 1)
        accepted = self.client.post(reverse("archives:import"), {"action": "confirm", "token": token})
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(Workspace.objects.count(), 2)

    def test_deleted_photo_cleanup_happens_after_commit(self):
        path = Path(self.item.photo.path)
        with self.captureOnCommitCallbacks(execute=True):
            self.item.delete()
            self.assertTrue(path.exists())
        self.assertFalse(path.exists())


class OperationalBackupTests(SimpleTestCase):
    def test_backup_restore_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.sqlite3"
            with sqlite3.connect(source) as db:
                db.execute("CREATE TABLE sentinel (value text)")
                db.execute("INSERT INTO sentinel VALUES ('keep me')")
            media = root / "media"
            media.mkdir()
            (media / "photo.jpg").write_bytes(b"original file")
            backup = root / "backup.zip"
            with (
                override_settings(
                    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(source)}},
                    MEDIA_ROOT=media,
                ),
                redirect_stdout(io.StringIO()),
            ):
                call_command("backup_inventory", output=str(backup))
                with self.assertRaises(CommandError):
                    call_command("backup_inventory", output=str(backup))
            target = root / "restored.sqlite3"
            files = root / "restored-media"
            with redirect_stdout(io.StringIO()):
                call_command(
                    "restore_inventory", archive=str(backup), database=str(target), media_root=str(files)
                )
                with self.assertRaises(CommandError):
                    call_command(
                        "restore_inventory", archive=str(backup), database=str(target), media_root=str(files)
                    )
            with sqlite3.connect(target) as db:
                self.assertEqual(db.execute("SELECT value FROM sentinel").fetchone()[0], "keep me")
            self.assertEqual((files / "photo.jpg").read_bytes(), b"original file")

    def test_restore_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../outside", b"evil")
                zf.writestr("backup.json", "{}")
            with self.assertRaises(CommandError):
                call_command(
                    "restore_inventory",
                    archive=str(archive),
                    database=str(root / "new.db"),
                    media_root=str(root / "new-media"),
                )
            self.assertFalse((root / "new.db").exists())
