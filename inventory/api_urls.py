from django.urls import path
from ninja import NinjaAPI
from inventory.api import router

api = NinjaAPI(
    title="HomeInventory API",
    version="1.0.0",
    description="API для сканирования QR-кодов и управления инвентарём",
)

api.add_router("/items/", router)

urlpatterns = [
    path("", api.urls),
]