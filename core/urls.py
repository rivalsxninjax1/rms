from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, LocationViewSet
app_name = "core"

router = DefaultRouter()
router.register('organizations', OrganizationViewSet)
router.register('locations', LocationViewSet)

urlpatterns = router.urls
