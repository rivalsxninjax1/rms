from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import Organization, Location
from .serializers import OrganizationSerializer, LocationSerializer

class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.select_related('organization').all()
    serializer_class = LocationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['organization', 'is_active']
