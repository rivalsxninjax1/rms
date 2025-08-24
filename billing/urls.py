from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, PaymentReceiptViewSet, InvoiceSequenceViewSet

router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'payment-receipts', PaymentReceiptViewSet, basename='payment-receipt')
router.register(r'invoice-sequences', InvoiceSequenceViewSet, basename='invoice-sequence')
app_name = "billing"

urlpatterns = [
    path('', include(router.urls)),
]
