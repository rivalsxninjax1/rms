from __future__ import annotations
from rest_framework import serializers
from .models import Table, Reservation

class TableStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    table_number = serializers.CharField()
    capacity = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["available", "reserved", "busy"])
    hold_seconds = serializers.IntegerField(required=False, allow_null=True)
    reservation_id = serializers.IntegerField(required=False, allow_null=True)
    reservation_status = serializers.CharField(required=False, allow_blank=True)

class CreateReservationSerializer(serializers.Serializer):
    table_id = serializers.IntegerField()
    date = serializers.DateField()
    time = serializers.TimeField()
    party_size = serializers.IntegerField(min_value=1)
    customer_name = serializers.CharField(max_length=200)
    customer_phone = serializers.CharField(max_length=20)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        # Basic capacity check using existing Table model
        try:
            table = Table.objects.get(pk=attrs["table_id"])
        except Table.DoesNotExist:
            raise serializers.ValidationError("Table not found.")
        if attrs["party_size"] > table.capacity:
            raise serializers.ValidationError("Party size exceeds table capacity.")
        return attrs

    def create(self, validated):
        request = self.context["request"]
        user = request.user
        table = Table.objects.get(pk=validated["table_id"])
        # Let your model default the status (often 'PENDING' or 'CONFIRMED')
        res = Reservation.objects.create(
            table=table,
            customer_name=validated["customer_name"],
            customer_phone=validated["customer_phone"],
            customer_email=validated.get("customer_email", ""),
            party_size=validated["party_size"],
            reservation_date=validated["date"],
            reservation_time=validated["time"],
            notes=validated.get("notes", ""),
            created_by=user,
        )
        return res

class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            "id","table","customer_name","customer_phone","customer_email",
            "party_size","reservation_date","reservation_time",
            "status","notes","created_by","created_at","updated_at",
        ]
        read_only_fields = ["created_by","created_at","updated_at"]
