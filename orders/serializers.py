# orders/serializers.py
from rest_framework import serializers
from orders.models import Order

# Optional import — only if payments app is present
try:
    from payments.models import Payment
except Exception:
    Payment = None


class PaymentMiniSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    is_paid = serializers.BooleanField()
    stripe_session_id = serializers.CharField()
    stripe_payment_intent = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class OrderListSerializer(serializers.ModelSerializer):
    """
    Compact read serializer for listing orders in a "My Orders" screen.
    Includes nested payment mini and invoice URL (if stored).
    """
    payment = serializers.SerializerMethodField()
    invoice_url = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "customer_name",
            "customer_email",
            "created_at",
            "invoice_url",
            "payment",
        ]

    def get_payment(self, obj):
        pay = getattr(obj, "payment", None)
        if not pay:
            return None
        return {
            "amount": pay.amount,
            "currency": pay.currency,
            "is_paid": bool(pay.is_paid),
            "stripe_session_id": pay.stripe_session_id,
            "stripe_payment_intent": pay.stripe_payment_intent,
            "created_at": pay.created_at,
            "updated_at": pay.updated_at,
        }

    def get_invoice_url(self, obj):
        inv = getattr(obj, "invoice_pdf", None)
        if not inv:
            return None
        try:
            request = self.context.get("request")
            url = inv.url
            return request.build_absolute_uri(url) if request else url
        except Exception:
            return None
