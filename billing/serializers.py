from rest_framework import serializers
from .models import Payment, PaymentReceipt, InvoiceSequence


class InvoiceSequenceSerializer(serializers.ModelSerializer):
    next_invoice_preview = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceSequence
        fields = ['id', 'location', 'prefix', 'next_number', 'padding', 'updated_at', 'next_invoice_preview']
        read_only_fields = ['updated_at', 'next_invoice_preview']

    def get_next_invoice_preview(self, obj):
        return obj.peek_next_invoice_no()


class PaymentSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'method', 'amount', 'reference', 'notes',
            'created_at', 'created_by'
        ]
        read_only_fields = ['created_at', 'created_by']


class PaymentReceiptSerializer(serializers.ModelSerializer):
    generated_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PaymentReceipt
        fields = [
            'id', 'order', 'receipt_file', 'file_name',
            'generated_at', 'generated_by'
        ]
        read_only_fields = ['generated_at', 'generated_by']

    def validate(self, attrs):
        # Optional: if a file is provided without file_name, we’ll auto-fill in model.save()
        return super().validate(attrs)
