from rest_framework.routers import DefaultRouter
from .views import TableViewSet, ReservationViewSet
app_name = "reservations"

router = DefaultRouter()
router.register('reservations/tables', TableViewSet)
router.register('reservations', ReservationViewSet)

urlpatterns = router.urls
