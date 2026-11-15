"""Private inventory workflows. Every object lookup is scoped to membership."""
import io
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import CharField, Q, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Cast, Replace
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from workspaces.access import accessible_workspaces, active_workspace, can_edit, can_manage
from .csv_export import csv_response
from .forms import CategoryForm, ContainerForm, ContainerMoveForm, FilterForm, ItemForm, ListingForm, LoanForm, LocationForm
from .models import Container, Item, Loan, PublicListing, normalize_search
from .services import checkout_item, move_container, move_item, return_loan


def navigation(request, workspace=None):
    workspace = workspace or active_workspace(request)
    return {"workspace": workspace, "available_workspaces": accessible_workspaces(request.user), "can_edit": can_edit(request.user, workspace), "can_manage": can_manage(request.user, workspace)}


def _item(request, pk=None, label_id=None):
    lookup = {"pk": pk} if pk is not None else {"label_id": label_id}
    item = get_object_or_404(Item.objects.select_related("workspace", "category", "location", "container__location").filter(workspace__in=accessible_workspaces(request.user)), **lookup)
    if request.session.get("workspace_id") != item.workspace_id:
        request.session["workspace_id"] = item.workspace_id
    return item


def _container(request, pk=None, label_id=None):
    lookup = {"pk": pk} if pk is not None else {"label_id": label_id}
    container = get_object_or_404(Container.objects.select_related("workspace", "location").filter(workspace__in=accessible_workspaces(request.user)), **lookup)
    if request.session.get("workspace_id") != container.workspace_id:
        request.session["workspace_id"] = container.workspace_id
    return container


def _require_edit(request, workspace):
    if not can_edit(request.user, workspace):
        raise PermissionDenied


def _form_page(request, form, title, workspace, back_url=None, status=200):
    return render(request, "inventory/form.html", {**navigation(request, workspace), "form": form, "title": title, "back_url": back_url or reverse("inventory:item-list")}, status=status)


@login_required
def item_list(request):
    workspace = active_workspace(request)
    form = FilterForm(request.GET or None, workspace=workspace)
    items = Item.objects.select_related("category", "location", "container__location").filter(workspace=workspace) if workspace else Item.objects.none()
    status = 200
    if form.is_bound:
        if form.is_valid():
            data = form.cleaned_data
            if data["q"]:
                items = items.filter(search_text__contains=normalize_search(data["q"]))
            for key in ("category", "container"):
                if data[key]:
                    items = items.filter(**{key: data[key]})
            if data["location"]:
                items = items.filter(Q(location=data["location"]) | Q(container__location=data["location"]))
        else:
            items = items.none()
            status = 400
    page = Paginator(items, 24).get_page(request.GET.get("page"))
    filters = request.GET.copy()
    filters.pop("page", None)
    return render(request, "inventory/item_list.html", {**navigation(request, workspace), "items": page.object_list, "page_obj": page, "filter_form": form, "categories": form.fields["category"].queryset, "locations": form.fields["location"].queryset, "containers": form.fields["container"].queryset, "query": request.GET.get("q", ""), "filter_query": filters.urlencode()}, status=status)


@login_required
def item_detail(request, pk):
    item = _item(request, pk=pk)
    active_loan = item.loans.filter(returned_at__isnull=True).select_related("borrower").first()
    listing = PublicListing.objects.filter(item=item).first() or PublicListing(item=item, workspace=item.workspace)
    return render(request, "inventory/item_detail.html", {**navigation(request, item.workspace), "item": item, "active_loan": active_loan, "loan_form": LoanForm(workspace=item.workspace), "listing_form": ListingForm(instance=listing), "movements": item.movements.select_related("actor", "from_location", "to_location")[:10]})


@login_required
def item_create(request):
    workspace = active_workspace(request)
    if workspace is None:
        return redirect("workspaces:workspace-create")
    _require_edit(request, workspace)
    form = ItemForm(request.POST or None, request.FILES or None, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        messages.success(request, "Вещь добавлена.")
        return redirect(item)
    return _form_page(request, form, "Добавить вещь", workspace, status=400 if request.method == "POST" else 200)


@login_required
def item_edit(request, pk):
    item = _item(request, pk=pk)
    _require_edit(request, item.workspace)
    form = ItemForm(request.POST or None, request.FILES or None, instance=item, workspace=item.workspace)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                current = Item.objects.select_for_update().get(pk=item.pk)
                desired = form.save(commit=False)
                updated = move_item(current, actor=request.user, location=desired.location, container=desired.container, expected_version=form.cleaned_data["expected_version"])
                for field in ("name", "description", "photo", "category", "purchase_date", "price"):
                    setattr(updated, field, getattr(desired, field))
                updated.save()
            messages.success(request, "Изменения сохранены.")
            return redirect(updated)
        except ValidationError as exc:
            form.add_error(None, exc)
    return _form_page(request, form, "Изменить вещь", item.workspace, item.get_absolute_url(), 400 if request.method == "POST" else 200)


@login_required
@require_POST
def item_delete(request, pk):
    item = _item(request, pk=pk)
    _require_edit(request, item.workspace)
    try:
        item.delete()
    except ProtectedError:
        messages.error(request, "У вещи есть история выдач. Сохраните её для учёта.")
        return redirect(item)
    messages.success(request, "Вещь удалена.")
    return redirect("inventory:item-list")


@login_required
def container_list(request):
    workspace = active_workspace(request)
    containers = Container.objects.filter(workspace=workspace).select_related("location") if workspace else Container.objects.none()
    return render(request, "inventory/container_list.html", {**navigation(request, workspace), "containers": containers})


@login_required
def container_detail(request, pk):
    container = _container(request, pk=pk)
    return render(request, "inventory/container_detail.html", {**navigation(request, container.workspace), "container": container, "items": container.items.select_related("category"), "move_form": ContainerMoveForm(container=container), "movements": container.movements.select_related("actor", "from_location", "to_location")[:10]})


@login_required
def container_create(request):
    workspace = active_workspace(request)
    if workspace is None:
        return redirect("workspaces:workspace-create")
    _require_edit(request, workspace)
    form = ContainerForm(request.POST or None, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        return redirect(form.save())
    return _form_page(request, form, "Добавить коробку", workspace, status=400 if request.method == "POST" else 200)


@login_required
def container_edit(request, pk):
    container = _container(request, pk=pk)
    _require_edit(request, container.workspace)
    form = ContainerForm(request.POST or None, instance=container, workspace=container.workspace)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                current = Container.objects.select_for_update().get(pk=container.pk)
                desired = form.save(commit=False)
                updated = move_container(current, actor=request.user, location=desired.location, expected_version=form.cleaned_data["expected_version"])
                updated.name, updated.description = desired.name, desired.description
                updated.save()
            return redirect(updated)
        except ValidationError as exc:
            form.add_error(None, exc)
    return _form_page(request, form, "Изменить коробку", container.workspace, container.get_absolute_url(), 400 if request.method == "POST" else 200)


@login_required
@require_POST
def container_move(request, pk):
    container = _container(request, pk=pk)
    _require_edit(request, container.workspace)
    form = ContainerMoveForm(request.POST, container=container)
    if form.is_valid():
        try:
            move_container(container, actor=request.user, location=form.cleaned_data["location"], expected_version=form.cleaned_data["expected_version"])
            messages.success(request, "Коробка и её содержимое перемещены.")
            return redirect(container)
        except ValidationError as exc:
            form.add_error(None, exc)
    return _form_page(request, form, "Переместить коробку", container.workspace, container.get_absolute_url(), 400)


def _simple_create(request, form_class, title):
    workspace = active_workspace(request)
    if workspace is None:
        return redirect("workspaces:workspace-create")
    _require_edit(request, workspace)
    form = form_class(request.POST or None, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("inventory:item-list")
    return _form_page(request, form, title, workspace, status=400 if request.method == "POST" else 200)


@login_required
def location_create(request):
    return _simple_create(request, LocationForm, "Добавить место")


@login_required
def category_create(request):
    return _simple_create(request, CategoryForm, "Добавить категорию")


@login_required
def export_csv(request):
    workspace = active_workspace(request)
    return csv_response(Item.objects.filter(workspace=workspace))


@login_required
def scanner_view(request):
    return render(request, "inventory/scanner.html", navigation(request))


@login_required
def labels(request):
    workspace = active_workspace(request)
    return render(request, "inventory/labels.html", {**navigation(request, workspace), "items": Item.objects.filter(workspace=workspace), "containers": Container.objects.filter(workspace=workspace)})


def _qr_response(subject):
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    parsed = urlsplit(base)
    if not parsed.netloc or parsed.scheme not in {"https", "http"}:
        raise Http404
    output = io.BytesIO()
    qrcode.make(base + subject.get_label_url()).save(output, format="PNG")
    response = HttpResponse(output.getvalue(), content_type="image/png")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def item_qr(request, pk):
    return _qr_response(_item(request, pk=pk))


@login_required
def container_qr(request, pk):
    return _qr_response(_container(request, pk=pk))


@login_required
def item_label(request, label_id):
    return redirect(_item(request, label_id=label_id))


@login_required
def container_label(request, label_id):
    return redirect(_container(request, label_id=label_id))


@login_required
@require_POST
def label_resolve(request):
    code = request.POST.get("code", "").strip().replace("-", "").lower()
    kind = request.POST.get("kind", "item")
    if kind not in {"item", "container"} or not re.fullmatch(r"[0-9a-f]{8,32}", code):
        return render(request, "inventory/scanner.html", {**navigation(request), "manual_error": "Введите код этикетки: от 8 шестнадцатеричных символов."}, status=400)
    model = Item if kind == "item" else Container
    objects = list(model.objects.filter(workspace__in=accessible_workspaces(request.user)).annotate(code=Replace(Cast("label_id", output_field=CharField()), Value("-"), Value(""))).filter(code__startswith=code)[:2])
    if len(objects) != 1:
        return render(request, "inventory/scanner.html", {**navigation(request), "manual_error": "Код не найден или неоднозначен. Уточните код и доступ к пространству."}, status=400)
    return redirect(objects[0])


@login_required
@require_POST
def loan_checkout(request, pk):
    item = _item(request, pk=pk)
    _require_edit(request, item.workspace)
    form = LoanForm(request.POST, workspace=item.workspace)
    if form.is_valid():
        try:
            checkout_item(item, actor=request.user, **form.cleaned_data)
            messages.success(request, "Вещь выдана участнику.")
            return redirect(item)
        except ValidationError as exc:
            form.add_error(None, exc)
    return _form_page(request, form, "Выдать вещь", item.workspace, item.get_absolute_url(), 400)


@login_required
@require_POST
def loan_return(request, pk):
    loan = get_object_or_404(Loan.objects.select_related("item", "workspace").filter(workspace__in=accessible_workspaces(request.user)), pk=pk)
    _require_edit(request, loan.workspace)
    return_loan(loan, actor=request.user)
    messages.success(request, "Возврат отмечен.")
    return redirect(loan.item)


@login_required
@require_POST
def listing_edit(request, pk):
    item = _item(request, pk=pk)
    if not can_manage(request.user, item.workspace):
        raise PermissionDenied
    listing = PublicListing.objects.filter(item=item).first() or PublicListing(item=item, workspace=item.workspace)
    form = ListingForm(request.POST, instance=listing)
    if form.is_valid():
        form.save()
        messages.success(request, "Настройки публикации сохранены.")
        return redirect(item)
    return _form_page(request, form, "Публичная карточка", item.workspace, item.get_absolute_url(), 400)


def public_listing(request, token):
    # Deliberately pass only the opt-in public whitelist, never the Item object.
    listing = get_object_or_404(PublicListing.objects.values("title", "description"), token=token, active=True)
    response = render(request, "inventory/public_listing.html", {"listing": listing})
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@login_required
def api_root(request):
    return JsonResponse({"name": "HomeInventory", "version": "2", "endpoints": {"item": "/api/items/{id}/", "home": "/", "scanner": "/scanner/"}})


@login_required
def api_item_detail(request, pk):
    item = _item(request, pk=pk)
    return JsonResponse({"id": item.pk, "name": item.name, "location": str(item.effective_location) if item.effective_location else None, "url": item.get_absolute_url(), "label_url": item.get_label_url()})


@login_required
def private_media(request, path):
    parts = PurePosixPath(path)
    if parts.is_absolute() or ".." in parts.parts or "\\" in path:
        raise Http404
    item = get_object_or_404(Item.objects.filter(workspace__in=accessible_workspaces(request.user)), photo=path)
    if not item.photo:
        raise Http404
    suffix = PurePosixPath(item.photo.name).suffix.lower()
    content_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(suffix, "application/octet-stream")
    try:
        file = item.photo.storage.open(item.photo.name, "rb")
    except (FileNotFoundError, OSError):
        raise Http404 from None
    response = FileResponse(file, content_type=content_type, as_attachment=content_type == "application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def _error(request, code, title):
    return render(request, "inventory/error.html", {"error_code": str(code), "error_title": title, "error_message": title, "error_details": "Вернитесь на главную страницу или проверьте доступ."}, status=code)


def page_not_found(request, exception):
    return _error(request, 404, "Страница не найдена")


def server_error(request):
    return _error(request, 500, "Внутренняя ошибка сервера")


def bad_request(request, exception):
    return _error(request, 400, "Неверный запрос")


def permission_denied(request, exception):
    return _error(request, 403, "Доступ запрещён")
