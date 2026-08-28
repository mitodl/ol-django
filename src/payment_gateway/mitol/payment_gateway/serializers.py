"""Serializers for PaymentGateway."""

from rest_framework import serializers


class BaseCartItemSerializer(serializers.Serializer):
    """Serialize the BaseCartItem."""

    unitprice = serializers.DecimalField(max_digits=9, decimal_places=2)
    quantity = serializers.IntegerField()
    taxable = serializers.DecimalField(max_digits=9, decimal_places=2)


class OrderSerializer(serializers.Serializer):
    """Serialize the Order."""

    username = serializers.CharField(max_length=255)
    ip_address = serializers.CharField(max_length=255)
    reference = serializers.CharField(max_length=255)
    email = serializers.CharField(max_length=255)
    items = BaseCartItemSerializer(many=True)
