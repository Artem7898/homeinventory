import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Проверить и восстановить offline backup в НОВЫЕ пути; существующие данные не заменяются."

    def add_arguments(self, parser):
        parser.add_argument("--archive", required=True)
        parser.add_argument("--database", required=True)
        parser.add_argument("--media-root", required=True)
        parser.add_argument("--max-bytes", type=int, default=10 * 1024**3)

    def handle(self, *args, **options):
        db = Path(options["database"]).resolve()
        media = Path(options["media_root"]).resolve()
        if db.exists() or media.exists():
            raise CommandError("Пути базы и media должны быть новыми и отсутствовать; перезапись запрещена.")
        if db.is_relative_to(media) or media.is_relative_to(db):
            raise CommandError("Пути базы и media не должны пересекаться.")
        db.parent.mkdir(parents=True, exist_ok=True)
        media.parent.mkdir(parents=True, exist_ok=True)
        created_db = created_media = False
        try:
            with (
                zipfile.ZipFile(options["archive"]) as zf,
                tempfile.TemporaryDirectory(dir=db.parent) as dbtemp,
                tempfile.TemporaryDirectory(dir=media.parent) as mediatemp,
            ):
                infos = zf.infolist()
                names = [x.filename for x in infos]
                if (
                    len(names) != len(set(names))
                    or len(names) > 100000
                    or sum(x.file_size for x in infos) > options["max_bytes"]
                ):
                    raise CommandError("Недопустимый размер или повторяющиеся файлы.")
                for info in infos:
                    path = PurePosixPath(info.filename)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or "\\" in info.filename
                        or stat.S_ISLNK(info.external_attr >> 16)
                        or info.flag_bits & 1
                    ):
                        raise CommandError("Недопустимый путь, ссылка или шифрование в backup.")
                    if info.filename not in {"backup.json", "database.sqlite3"} and (
                        not info.filename.startswith("media/") or path.parts == ("media",)
                    ):
                        raise CommandError("Неизвестный файл в backup.")
                if zf.getinfo("backup.json").file_size > 8 * 1024 * 1024:
                    raise CommandError("Manifest слишком велик.")
                manifest = json.loads(zf.read("backup.json"))
                if not isinstance(manifest, dict):
                    raise CommandError("Manifest должен быть объектом.")
                if (
                    manifest.get("schema_version") != 1
                    or manifest.get("kind") != "homeinventory-sqlite-backup"
                ):
                    raise CommandError("Неизвестный формат backup.")
                files = manifest["files"]
                if not isinstance(files, dict) or any(
                    not isinstance(v, dict)
                    or not isinstance(v.get("size"), int)
                    or not isinstance(v.get("sha256"), str)
                    for v in files.values()
                ):
                    raise CommandError("Неверные сведения о файлах.")
                if set(files) != set(names) - {"backup.json"} or "database.sqlite3" not in files:
                    raise CommandError("Набор файлов не совпадает с manifest.")
                staged_db = Path(dbtemp) / "database.sqlite3"
                staged_media = Path(mediatemp)
                for name, details in files.items():
                    dest = (
                        staged_db
                        if name == "database.sqlite3"
                        else staged_media.joinpath(*PurePosixPath(name).parts[1:])
                    )
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    size = 0
                    with zf.open(name) as src, dest.open("xb") as output:
                        for chunk in iter(lambda: src.read(1024 * 1024), b""):
                            digest.update(chunk)
                            size += len(chunk)
                            if size > options["max_bytes"]:
                                raise CommandError("Превышен лимит размера.")
                            output.write(chunk)
                    if size != details["size"] or digest.hexdigest() != details["sha256"]:
                        raise CommandError("Контрольная сумма или размер не совпадают.")
                with sqlite3.connect(staged_db) as connection:
                    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise CommandError("SQLite integrity_check не пройден.")
                # Exclusive creation, even if a destination appeared since validation.
                with db.open("xb") as output, staged_db.open("rb") as source:
                    created_db = True
                    shutil.copyfileobj(source, output)
                os.chmod(db, 0o600)
                media.mkdir(mode=0o700)
                created_media = True
                for path in staged_media.iterdir():
                    shutil.move(str(path), media / path.name)
            self.stdout.write(
                self.style.SUCCESS(
                    "Backup проверен и восстановлен в новые пути. Переключайте настройки только при остановленном приложении."
                )
            )
        except (
            OSError,
            sqlite3.Error,
            zipfile.BadZipFile,
            KeyError,
            ValueError,
            TypeError,
            CommandError,
        ) as exc:
            if created_db:
                db.unlink(missing_ok=True)
            if created_media:
                shutil.rmtree(media)
            raise CommandError(str(exc)) from exc
