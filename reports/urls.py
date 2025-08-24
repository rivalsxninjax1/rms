from rest_framework.routers import DefaultRouter
from .views import DailySalesViewSet, ShiftReportViewSet
app_name = "reports"

router = DefaultRouter()
router.register('reports/daily-sales', DailySalesViewSet)
router.register('reports/shift-reports', ShiftReportViewSet)

urlpatterns = router.urls