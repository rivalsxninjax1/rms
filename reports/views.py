from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import DailySales, ShiftReport
from .serializers import DailySalesSerializer, ShiftReportSerializer

class DailySalesViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailySales.objects.select_related('location').all()
    serializer_class = DailySalesSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['location', 'date']

class ShiftReportViewSet(viewsets.ModelViewSet):
    queryset = ShiftReport.objects.select_related('location', 'user').all()
    serializer_class = ShiftReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['location', 'user', 'is_closed']