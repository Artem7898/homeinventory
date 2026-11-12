from django.urls import path
from . import archive_views

app_name = "archives"
urlpatterns = [
    path("import/", archive_views.import_archive, name="import"),
    path("<int:workspace_id>/export/", archive_views.export, name="export"),
]
