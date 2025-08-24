from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Payment, PaymentReceipt, InvoiceSequence
from .serializers import PaymentSerializer, PaymentReceiptSerializer, InvoiceSequenceSerializer


class IsAuthenticatedOrReadOnly(permissions.IsAuthenticatedOrReadOnly):
    pass


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('order', 'created_by').all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ['method', 'order']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PaymentReceiptViewSet(viewsets.ModelViewSet):
    queryset = PaymentReceipt.objects.select_related('order', 'generated_by').all()
    serializer_class = PaymentReceiptSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ['order']

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)


class InvoiceSequenceViewSet(viewsets.ModelViewSet):
    queryset = InvoiceSequence.objects.select_related('location').all()
    serializer_class = InvoiceSequenceSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ['location', 'prefix']

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def consume(self, request, pk=None):
        seq = self.get_object()
        number = seq.consume_next_invoice_no()
        return Response({'invoice_no': number})
