"""Bounded, portable workspace archives; never extracts paths supplied by a client."""

import hashlib
import io
import json
import re
import stat
import uuid
import zipfile
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction

MAX_UPLOAD = 25 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
MAX_FILES = 2000
MAX_RECORDS = 10000
PHOTO_NAME = re.compile(r"photos/[0-9a-f-]{36}\.(?:jpg|png)\Z")


def _rows(manifest, key):
    rows = manifest.get(key)
    if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
        raise ValidationError(f"Недопустимый раздел архива: {key}.")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in seen:
            raise ValidationError(f"Повторяющийся или неверный идентификатор: {key}.")
        seen.add(row["id"])
        if (
            not isinstance(row.get("name"), str)
            or not row["name"].strip()
            or len(row["name"]) > (200 if key in {"items", "containers"} else 100)
        ):
            raise ValidationError("Проверьте названия записей архива.")
        if not isinstance(row.get("description", ""), str) or len(row.get("description", "")) > 100000:
            raise ValidationError("Недопустимое описание.")
    return rows


def inspect_archive(data):
    """Validate all metadata, references and bytes before opening a transaction."""
    if len(data) > MAX_UPLOAD:
        raise ValidationError("Архив больше 25 МБ.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
        if len(infos) > MAX_FILES or len({x.filename for x in infos}) != len(infos):
            raise ValidationError("Слишком много файлов или повторяющиеся имена.")
        if sum(x.file_size for x in infos) > MAX_EXPANDED:
            raise ValidationError("Распакованный архив превышает 100 МБ.")
        for info in infos:
            if info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16):
                raise ValidationError("Зашифрованные файлы и ссылки запрещены.")
            if info.filename != "manifest.json" and not PHOTO_NAME.fullmatch(info.filename):
                raise ValidationError("Недопустимый путь в архиве.")
            if info.file_size > MAX_UPLOAD or info.file_size > max(1, info.compress_size) * 200:
                raise ValidationError("Недопустимая степень сжатия.")
        manifest_info = zf.getinfo("manifest.json")
        if manifest_info.file_size > 8 * 1024 * 1024:
            raise ValidationError("Описание архива слишком велико.")
        manifest = json.loads(zf.read("manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
            raise ValidationError("Неподдерживаемая версия архива.")
        space = manifest.get("workspace", {})
        if (
            not isinstance(space, dict)
            or not isinstance(space.get("name"), str)
            or not 1 <= len(space["name"].strip()) <= 160
        ):
            raise ValidationError("Нет названия пространства.")
        if space.get("kind") not in {"home", "workshop", "community"}:
            raise ValidationError("Неизвестный тип пространства.")
        rows = {key: _rows(manifest, key) for key in ("categories", "locations", "containers", "items")}
        ids = {key: {r["id"] for r in value} for key, value in rows.items()}
        for row in rows["categories"]:
            if not isinstance(row.get("icon", ""), str) or len(row.get("icon", "")) > 50:
                raise ValidationError("Неверное обозначение категории.")
        for row in rows["items"]:
            if row.get("price") is not None and not isinstance(row["price"], str):
                raise ValidationError("Неверный формат цены.")
            forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False).clean(
                row.get("price")
            )
            value = row.get("purchase_date")
            if value is not None and not isinstance(value, str):
                raise ValidationError("Неверная дата покупки.")
            forms.DateField(required=False, input_formats=["%Y-%m-%d"]).clean(value)
        refs = {
            "locations": {"parent": "locations"},
            "containers": {"location": "locations"},
            "items": {"category": "categories", "location": "locations", "container": "containers"},
        }
        for key, fields in refs.items():
            for row in rows[key]:
                for field, target in fields.items():
                    ref = row.get(field)
                    if ref is not None and (not isinstance(ref, str) or ref not in ids[target]):
                        raise ValidationError("В архиве есть ссылка на отсутствующую запись.")
                if key == "items" and row.get("location") and row.get("container"):
                    raise ValidationError("Вещь не может одновременно быть в коробке и напрямую в комнате.")
        parents = {r["id"]: r.get("parent") for r in rows["locations"]}
        for node in parents:
            chain = set()
            while node:
                if node in chain or len(chain) > 100:
                    raise ValidationError("Цикл или слишком глубокая иерархия мест.")
                chain.add(node)
                node = parents[node]
        files = {}
        used = set()
        for row in rows["items"]:
            photo = row.get("photo")
            if photo is None:
                continue
            if (
                not isinstance(photo, dict)
                or not isinstance(photo.get("path"), str)
                or not PHOTO_NAME.fullmatch(photo["path"])
            ):
                raise ValidationError("Неверное описание фотографии.")
            if photo["path"] in used:
                raise ValidationError("Повтор фотографии в архиве.")
            used.add(photo["path"])
            content = zf.read(photo["path"])
            if hashlib.sha256(content).hexdigest() != photo.get("sha256"):
                raise ValidationError("Контрольная сумма фотографии не совпадает.")
            # The same upload validation/re-encoding contract as ordinary forms.
            from inventory.forms import clean_photo

            files[row["id"]] = clean_photo(ContentFile(content, name=photo["path"].split("/")[-1]))
        if used != {x.filename for x in infos if x.filename != "manifest.json"}:
            raise ValidationError("В архиве есть неописанные файлы.")
        return manifest, files
    except ValidationError:
        raise
    except (
        zipfile.BadZipFile,
        KeyError,
        ValueError,
        TypeError,
        OSError,
        RuntimeError,
        RecursionError,
    ) as exc:
        raise ValidationError("Повреждённый или неподдерживаемый архив.") from exc


def export_workspace(workspace):
    from categories.models import Category
    from inventory.models import Container, Item
    from locations.models import Location

    data = {"schema_version": 1, "workspace": {"name": workspace.name, "kind": workspace.kind}}

    def ref(value):
        return str(value) if value is not None else None

    data["categories"] = [
        {"id": str(x.pk), "name": x.name, "icon": x.icon}
        for x in Category.objects.filter(workspace=workspace).order_by("pk")
    ]
    data["locations"] = [
        {"id": str(x.pk), "name": x.name, "description": x.description, "parent": ref(x.parent_id)}
        for x in Location.objects.filter(workspace=workspace).order_by("pk")
    ]
    data["containers"] = [
        {
            "id": str(x.pk),
            "name": x.name,
            "description": x.description,
            "location": ref(x.location_id),
            "label_id": str(x.label_id),
        }
        for x in Container.objects.filter(workspace=workspace).order_by("pk")
    ]
    data["items"] = []
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        total = 0
        for item in Item.objects.filter(workspace=workspace).order_by("pk").iterator(chunk_size=200):
            row = {
                "id": str(item.pk),
                "name": item.name,
                "description": item.description,
                "category": ref(item.category_id),
                "location": ref(item.location_id),
                "container": ref(item.container_id),
                "price": str(item.price) if item.price is not None else None,
                "purchase_date": item.purchase_date.isoformat() if item.purchase_date else None,
                "label_id": str(item.label_id),
                "photo": None,
            }
            if item.photo:
                with item.photo.open("rb") as f:
                    content = f.read(MAX_UPLOAD + 1)
                total += len(content)
                if total > MAX_UPLOAD:
                    raise ValidationError(
                        "Фотографии превышают лимит веб-архива 25 МБ. Используйте серверную резервную копию."
                    )
                # Export refuses stale/missing/unvalidated image paths instead of silently dropping data.
                from inventory.forms import clean_photo

                normalized = clean_photo(ContentFile(content, name=item.photo.name))
                content = normalized.read()
                suffix = ".png" if normalized.name.lower().endswith(".png") else ".jpg"
                path = f"photos/{uuid.uuid4()}{suffix}"
                zf.writestr(path, content)
                row["photo"] = {"path": path, "sha256": hashlib.sha256(content).hexdigest()}
            data["items"].append(row)
            if len(data["items"]) > MAX_RECORDS:
                raise ValidationError("Слишком много записей для веб-архива.")
        zf.writestr("manifest.json", json.dumps(data, ensure_ascii=False))
    result = target.getvalue()
    inspect_archive(result)
    return result


def import_workspace(data, *, user):
    """Import into a new private space; never trusts exported user IDs or permissions."""
    from categories.models import Category
    from inventory.models import Container, Item
    from locations.models import Location
    from workspaces.models import Membership, Workspace

    manifest, files = inspect_archive(data)
    key = hashlib.sha256(str(user.pk).encode() + b":" + hashlib.sha256(data).digest()).hexdigest()
    existing = Workspace.objects.filter(import_key=key).first()
    if existing:
        if not Membership.objects.filter(workspace=existing, user=user, role="owner").exists():
            raise ValidationError("Ранее импортированный архив больше не доступен.")
        return existing, False
    saved_files = []
    try:
        with transaction.atomic():
            space = Workspace.objects.create(
                name=manifest["workspace"]["name"], kind=manifest["workspace"]["kind"], import_key=key
            )
            Membership.objects.create(workspace=space, user=user, role="owner")
            maps = {key: {} for key in ("categories", "locations", "containers", "items")}
            for row in manifest["categories"]:
                obj = Category(workspace=space, name=row["name"], icon=row.get("icon", ""))
                obj.full_clean()
                obj.save()
                maps["categories"][row["id"]] = obj
            for row in manifest["locations"]:
                obj = Location.objects.create(
                    workspace=space, name=row["name"], description=row.get("description", "")
                )
                maps["locations"][row["id"]] = obj
            for row in manifest["locations"]:
                obj = maps["locations"][row["id"]]
                obj.parent = maps["locations"].get(row.get("parent"))
                obj.full_clean()
                obj.save()
            for row in manifest["containers"]:
                obj = Container(
                    workspace=space,
                    name=row["name"],
                    description=row.get("description", ""),
                    location=maps["locations"].get(row.get("location")),
                )
                obj.full_clean()
                obj.save()
                maps["containers"][row["id"]] = obj
            for row in manifest["items"]:
                try:
                    price = Decimal(row["price"]) if row.get("price") is not None else None
                except (InvalidOperation, TypeError):
                    raise ValidationError("Неверная цена в архиве.")
                obj = Item(
                    workspace=space,
                    name=row["name"],
                    description=row.get("description", ""),
                    category=maps["categories"].get(row.get("category")),
                    location=maps["locations"].get(row.get("location")),
                    container=maps["containers"].get(row.get("container")),
                    price=price,
                    purchase_date=row.get("purchase_date"),
                )
                if row["id"] in files:
                    obj.photo = files[row["id"]]
                obj.full_clean()
                try:
                    obj.save()
                finally:
                    if obj.photo and obj.photo._committed:
                        saved_files.append((obj.photo.storage, obj.photo.name))
        return space, True
    except Exception as exc:
        for storage, name in saved_files:
            storage.delete(name)
        if isinstance(exc, IntegrityError):
            existing = Workspace.objects.filter(
                import_key=key, memberships__user=user, memberships__role="owner"
            ).first()
            if existing:
                return existing, False
        raise
