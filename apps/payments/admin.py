from django.contrib import admin
from .models import PaymentMethod, Transaction, LockerCredit, Invoice


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['member', 'method_type', 'brand', 'last4', 'is_default', 'created_at']
    list_filter = ['method_type', 'is_default', 'brand']
    search_fields = ['member__email', 'last4']
    raw_id_fields = ['member']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'member', 'description', 'amount', 'status', 'created_at']
    list_filter = ['status', 'transaction_type', 'created_at']
    search_fields = ['transaction_id', 'member__email', 'description']
    raw_id_fields = ['member', 'payment_method']
    date_hierarchy = 'created_at'


@admin.register(LockerCredit)
class LockerCreditAdmin(admin.ModelAdmin):
    list_display = ['member', 'balance', 'max_cap', 'updated_at']
    search_fields = ['member__email']
    raw_id_fields = ['member']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'member', 'total', 'status', 'issued_at']
    list_filter = ['status']
    search_fields = ['invoice_number', 'member__email']
    raw_id_fields = ['member', 'transaction']