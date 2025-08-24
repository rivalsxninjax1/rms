from rest_framework.routers import DefaultRouter
from .views import SupplierViewSet, InventoryItemViewSet

router = DefaultRouter()
router.register('inventory/suppliers', SupplierViewSet)
router.register('inventory/items', InventoryItemViewSet)

urlpatterns = router.urls
