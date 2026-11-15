"""Offline operational backup. Operators must stop writers before invoking it."""

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Создать резервную копию SQLite и media после остановки записывающих процессов."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3" or db["NAME"] == ":memory:":
            raise CommandError(
                "Команда поддерживает файловую SQLite. Для PostgreSQL используйте pg_dump и копию MEDIA_ROOT в режиме обслуживания."
            )
        source = Path(db["NAME"]).resolve()
        target = Path(options["output"]).resolve()
        media = Path(settings.MEDIA_ROOT).resolve()
        if not source.is_file():
            raise CommandError("Файл базы данных отсутствует.")
        if target == source or target.is_relative_to(media):
            raise CommandError("Архив должен находиться вне базы данных и media.")
        owned = False
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            owned = True
            with os.fdopen(fd, "wb") as output, tempfile.TemporaryDirectory() as temp:
                snapshot = Path(temp) / "database.sqlite3"
                with (
                    sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src,
                    sqlite3.connect(snapshot) as dst,
                ):
                    src.backup(dst)
                entries = [(snapshot, "database.sqlite3")]
                if media.exists():
                    for path in sorted(media.rglob("*")):
                        if path.is_symlink():
                            raise CommandError("В media обнаружена ссылка; архивирование остановлено.")
                        if path.is_file():
                            entries.append((path, "media/" + path.relative_to(media).as_posix()))
                manifest = {"schema_version": 1, "kind": "homeinventory-sqlite-backup", "files": {}}
                with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
                    for path, name in entries:
                        digest = hashlib.sha256()
                        size = 0
                        with path.open("rb") as src, zf.open(name, "w") as dest:
                            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                                digest.update(chunk)
                                size += len(chunk)
                                dest.write(chunk)
                        manifest["files"][name] = {"sha256": digest.hexdigest(), "size": size}
                    zf.writestr("backup.json", json.dumps(manifest))
            self.stdout.write(
                self.style.SUCCESS(
                    "Резервная копия создана. Храните её как секрет: она содержит учётные записи и личные файлы."
                )
            )
        except (OSError, sqlite3.Error, zipfile.BadZipFile, CommandError) as exc:
            if owned:
                target.unlink(missing_ok=True)
            raise CommandError(str(exc)) from exc
