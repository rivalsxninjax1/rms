# orders/serializers.py
from rest_framework import serializers


class AddCartItemSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class RemoveCartItemSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()


class CartLineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    quantity = serializers.IntegerField()
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2)


class CartSerializer(serializers.Serializer):
    items = CartLineSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
