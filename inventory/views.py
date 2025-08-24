from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import Supplier, InventoryItem
from .serializers import SupplierSerializer, InventoryItemSerializer

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']

class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.select_related('supplier', 'location').all()
    serializer_class = InventoryItemSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['location', 'supplier', 'is_active', 'unit']
