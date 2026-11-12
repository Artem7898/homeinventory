"""One spreadsheet-safe CSV policy shared by the user UI and admin."""
import csv

from django.http import HttpResponse


def safe_cell(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    # Spreadsheet applications may ignore leading whitespace before a formula.
    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def csv_response(queryset, filename="inventory.csv"):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Название", "Описание", "Категория", "Место", "Коробка", "Цена", "Дата покупки"])
    queryset = queryset.select_related("category", "location", "container__location")
    for item in queryset.iterator(chunk_size=500):
        location = item.container.location if item.container_id else item.location
        writer.writerow([safe_cell(item.name), safe_cell(item.description), safe_cell(item.category.name if item.category_id else ""), safe_cell(location.name if location else ""), safe_cell(item.container.name if item.container_id else ""), item.price if item.price is not None else "", item.purchase_date or ""])
    return response
