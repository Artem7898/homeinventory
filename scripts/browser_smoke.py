#!/usr/bin/env python3
"""Exercise the real UI and local QR decoder against a disposable SQLite server."""

from concurrent.futures import ThreadPoolExecutor
import io
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory(prefix="homeinventory-browser-") as temp:
        temp = Path(temp)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        os.environ.update(
            DJANGO_SETTINGS_MODULE="config.test_settings",
            SQLITE_PATH=str(temp / "db.sqlite3"),
            MEDIA_ROOT=str(temp / "media"),
            DEBUG="True",
            PUBLIC_BASE_URL=origin,
        )
        os.environ.pop("DATABASE_URL", None)
        import django

        django.setup()
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from PIL import Image
        from workspaces.models import Workspace, Membership
        from inventory.models import Item, Container
        from locations.models import Location

        call_command("migrate", interactive=False, stdout=io.StringIO(), verbosity=0)
        password = secrets.token_urlsafe(20)
        User = get_user_model()
        owner = User.objects.create_user("browser-owner", password=password)
        viewer = User.objects.create_user("browser-viewer", password=password)
        User.objects.create_user("browser-outsider", password=password)
        photo = temp / "photo.png"
        Image.new("RGB", (80, 80), "blue").save(photo)
        with (temp / "server.log").open("w") as log:
            server = subprocess.Popen(
                [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload", "--insecure"],
                cwd=ROOT,
                env=os.environ.copy(),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError((temp / "server.log").read_text())
                    try:
                        with urllib.request.urlopen(origin + "/health/", timeout=1) as response:
                            if response.status == 200:
                                break
                    except (OSError, urllib.error.HTTPError):
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Disposable server did not become ready.")
                with ThreadPoolExecutor(max_workers=1) as database_thread, sync_playwright() as p:
                    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or shutil.which("chromium")
                    browser = p.chromium.launch(
                        headless=True, **({"executable_path": executable} if executable else {})
                    )
                    context = browser.new_context(viewport={"width": 390, "height": 844})
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))

                    def login(username):
                        page.goto(origin + "/accounts/login/")
                        page.locator("[name=username]").fill(username)
                        page.locator("[name=password]").fill(password)
                        page.locator("main form button[type=submit]").first.click()
                        page.wait_for_url(lambda u: "/accounts/login/" not in str(u))

                    login("browser-owner")
                    page.goto(origin + "/spaces/add/")
                    page.locator("[name=name]").fill("Семейное пространство")
                    page.locator("[name=kind]").select_option("home")
                    page.locator("main form button[type=submit]").first.click()
                    page.wait_for_url(origin + "/")
                    space = database_thread.submit(
                        lambda: Workspace.objects.get(memberships__user=owner)
                    ).result()
                    database_thread.submit(
                        lambda: Membership.objects.create(workspace=space, user=viewer, role="viewer")
                    ).result()
                    page.goto(origin + "/locations/add/")
                    page.locator("[name=name]").fill("Кладовка")
                    page.locator("main form button[type=submit]").first.click()
                    page.wait_for_url(origin + "/")
                    location = database_thread.submit(
                        lambda: Location.objects.get(workspace=space, name="Кладовка")
                    ).result()
                    page.goto(origin + "/containers/add/")
                    page.locator("[name=name]").fill("Сезонная коробка")
                    page.locator("[name=location]").select_option(str(location.pk))
                    page.locator("main form button[type=submit]").first.click()
                    page.wait_for_url("**/containers/*/")
                    box = database_thread.submit(lambda: Container.objects.get(workspace=space)).result()
                    page.goto(origin + "/item/add/")
                    page.locator("[name=name]").fill("Паспорт")
                    page.locator("[name=description]").fill("Частная заметка")
                    page.locator("[name=container]").select_option(str(box.pk))
                    page.locator("[name=price]").fill("0")
                    page.locator("[name=photo]").set_input_files(photo)
                    page.locator("main form button[type=submit]").first.click()
                    page.wait_for_url("**/item/*/")
                    item = database_thread.submit(lambda: Item.objects.get(workspace=space)).result()
                    assert page.locator("h1").inner_text() == "Паспорт"
                    assert page.locator(".detail-photo").evaluate("(img)=>img.complete && img.naturalWidth>0")
                    page.goto(origin + "/search/?q=паспорт")
                    assert page.locator(".item-card").count() == 1
                    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
                    qr = page.request.get(origin + f"/item/{item.pk}/qr.png")
                    assert qr.status == 200
                    qrfile = temp / "label.png"
                    qrfile.write_bytes(qr.body())
                    page.goto(origin + "/scanner/")
                    assert (
                        page.evaluate("HomeInventoryScanner.safeDestination('javascript:alert(1)')") is None
                    )
                    assert (
                        page.evaluate(
                            "HomeInventoryScanner.safeDestination('https://external.example/item/1/')"
                        )
                        is None
                    )
                    # Decode the actual generated PNG with the vendored library (no camera stub).
                    page.locator("#scanner-file").set_input_files(qrfile)
                    page.wait_for_url(origin + f"/item/{item.pk}/", timeout=15000)
                    page.goto(origin + "/labels/")
                    assert page.locator("img").count() >= 2
                    for image in page.locator("img").all():
                        assert image.evaluate("(img)=>img.complete && img.naturalWidth>0")
                    # A registered outsider still cannot read item or media.
                    outsider = browser.new_context()
                    outsider_page = outsider.new_page()
                    outsider_page.goto(origin + "/accounts/login/")
                    outsider_page.locator("[name=username]").fill("browser-outsider")
                    outsider_page.locator("[name=password]").fill(password)
                    outsider_page.locator("main form button[type=submit]").first.click()
                    outsider_page.wait_for_url(lambda u: "/accounts/login/" not in str(u))
                    assert outsider_page.request.get(origin + f"/item/{item.pk}/").status == 404
                    assert outsider_page.request.get(origin + item.photo.url).status == 404
                    outsider.close()
                    assert not errors, errors
                    browser.close()
                print(
                    "PASS browser: login, space/location/container creation, photo upload, Unicode search, private media, QR PNG file decode, label print page, tenant isolation, mobile overflow and scanner URL validation."
                )
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    main()
