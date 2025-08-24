from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import Table, Reservation
from .serializers import TableSerializer, ReservationSerializer

class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.select_related('location').all()
    serializer_class = TableSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['location', 'is_active', 'capacity']

class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.select_related('location', 'table', 'created_by').all()
    serializer_class = ReservationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['location', 'status', 'reservation_date', 'table']
