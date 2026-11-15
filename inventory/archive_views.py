import hashlib
import os
import stat
import tempfile
import time
import uuid
from pathlib import Path

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from workspaces.access import can_manage, accessible_workspaces

from .archive import MAX_UPLOAD, export_workspace, import_workspace, inspect_archive


class ArchiveForm(forms.Form):
    archive = forms.FileField(
        label="ZIP-архив каталога",
        help_text="До 25 МБ. Данные будут добавлены в новое приватное пространство.",
    )


def staging_directory():
    path = Path(tempfile.gettempdir()) / "homeinventory-imports"
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValidationError("Каталог временного импорта недоступен. Обратитесь к оператору.")
    # Bounded lifetime even if the user abandons confirmation.
    for old in path.glob("*.zip"):
        if old.stat().st_mtime < time.time() - 600:
            old.unlink(missing_ok=True)
    return path


@login_required
@require_http_methods(["GET"])
def export(request, workspace_id):
    workspace = get_object_or_404(accessible_workspaces(request.user), pk=workspace_id)
    if not can_manage(request.user, workspace):
        raise PermissionDenied
    try:
        data = export_workspace(workspace)
    except (ValidationError, OSError) as exc:
        messages.error(
            request,
            "; ".join(exc.messages)
            if isinstance(exc, ValidationError)
            else "Не удалось прочитать фотографии. Проверьте хранилище.",
        )
        return redirect("inventory:item-list")
    response = HttpResponse(data, content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="inventory-catalog.zip"'
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def import_archive(request):
    form = ArchiveForm(request.POST or None, request.FILES or None)
    preview = None
    token = None
    if request.method == "POST":
        try:
            if request.POST.get("action") == "confirm":
                payload = signing.loads(request.POST.get("token", ""), salt="catalog-import", max_age=600)
                if payload["user"] != request.user.pk or payload["session"] != request.session.session_key:
                    raise ValidationError("Подтверждение принадлежит другому сеансу.")
                name = payload["file"]
                if str(uuid.UUID(name[:-4])) + ".zip" != name:
                    raise ValidationError("Недопустимое подтверждение.")
                path = staging_directory() / name
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != payload["sha256"]:
                    raise ValidationError("Контрольная сумма архива не совпадает.")
                try:
                    workspace, created = import_workspace(data, user=request.user)
                finally:
                    path.unlink(missing_ok=True)
                request.session["workspace_id"] = workspace.pk
                messages.success(
                    request,
                    "Каталог импортирован."
                    if created
                    else "Этот архив уже был импортирован; открыто существующее пространство.",
                )
                return redirect("inventory:item-list")
            if form.is_valid():
                upload = form.cleaned_data["archive"]
                if upload.size > MAX_UPLOAD:
                    raise ValidationError("Архив больше 25 МБ.")
                data = upload.read(MAX_UPLOAD + 1)
                manifest, _ = inspect_archive(data)
                if not request.session.session_key:
                    request.session.save()
                filename = f"{uuid.uuid4()}.zip"
                path = staging_directory() / filename
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                token = signing.dumps(
                    {
                        "file": filename,
                        "user": request.user.pk,
                        "session": request.session.session_key,
                        "sha256": hashlib.sha256(data).hexdigest(),
                    },
                    salt="catalog-import",
                )
                preview = {
                    "name": manifest["workspace"]["name"],
                    "categories": len(manifest["categories"]),
                    "locations": len(manifest["locations"]),
                    "containers": len(manifest["containers"]),
                    "items": len(manifest["items"]),
                }
        except (ValidationError, signing.BadSignature, KeyError, ValueError, OSError) as exc:
            form.add_error(
                None,
                "; ".join(exc.messages)
                if isinstance(exc, ValidationError)
                else "Архив или подтверждение недействительны. Загрузите файл заново.",
            )
    return render(
        request, "inventory/archive_import.html", {"form": form, "preview": preview, "token": token}
    )
