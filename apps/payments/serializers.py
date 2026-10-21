from rest_framework import serializers
from .models import PaymentMethod, Transaction, LockerCredit, Invoice


class PaymentMethodSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source='get_method_type_display', read_only=True)

    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'method_type', 'method_display', 'is_default',
            'brand', 'last4', 'expiry_month', 'expiry_year',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    member_email = serializers.EmailField(source='member.email', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_id', 'description', 'transaction_type',
            'amount', 'tax_amount', 'subtotal',
            'payment_method_label', 'status',
            'member_name', 'member_email',
            'created_at', 'settled_at',
        ]


class TransactionListSerializer(serializers.ModelSerializer):
    """Lighter version for lists."""
    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_id', 'description', 'transaction_type',
            'amount', 'status', 'payment_method_label', 'created_at', 'settled_at',
        ]


class LockerCreditSerializer(serializers.ModelSerializer):
    percent_of_cap = serializers.SerializerMethodField()

    class Meta:
        model = LockerCredit
        fields = [
            'id', 'balance', 'max_cap', 'percent_of_cap', 'updated_at',
        ]

    def get_percent_of_cap(self, obj):
        if obj.max_cap > 0:
            return round((obj.balance / obj.max_cap) * 100, 1)
        return 0


class InvoiceSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'description',
            'amount', 'tax_amount', 'total',
            'status', 'member_name',
            'issued_at', 'due_at', 'paid_at',
        ]