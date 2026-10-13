from django.db import models
from django.conf import settings
from decimal import Decimal


class PaymentMethod(models.Model):
    """Saved payment methods for a member."""
    METHOD_CHOICES = [
        ('card', 'Credit/Debit Card'),
        ('apple_pay', 'Apple Pay'),
        ('google_pay', 'Google Pay'),
        ('locker_credit', 'Locker Credit'),
        ('cash', 'Cash / Counter'),
    ]

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_methods',
    )
    method_type = models.CharField(max_length=20, choices=METHOD_CHOICES)
    is_default = models.BooleanField(default=False)

    # Card details (masked)
    brand = models.CharField(max_length=20, blank=True)   # Visa, Mastercard
    last4 = models.CharField(max_length=4, blank=True)
    expiry_month = models.IntegerField(null=True, blank=True)
    expiry_year = models.IntegerField(null=True, blank=True)

    # Gateway reference (Stripe customer/payment-method ID)
    gateway_token = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_methods'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        if self.method_type == 'card':
            return f"{self.brand} •••• {self.last4}"
        return self.get_method_type_display()


class Transaction(models.Model):
    """A single financial transaction."""
    TYPE_CHOICES = [
        ('subscription', 'Subscription'),
        ('coaching', 'Coaching'),
        ('retail', 'Retail'),
        ('recovery', 'Recovery'),
        ('refund', 'Refund'),
        ('topup', 'Locker Top-Up'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('settled', 'Settled'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    ]

    # Who
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='transactions',
    )

    # ID
    transaction_id = models.CharField(max_length=30, unique=True)  # #TXN-99410

    # Description
    description = models.CharField(max_length=200)
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    # Amount
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Payment method
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions',
    )
    payment_method_label = models.CharField(max_length=60, blank=True)  # "Visa •••• 4242"

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Gateway
    gateway_reference = models.CharField(max_length=100, blank=True)  # Stripe charge ID

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_id} — ${self.amount} ({self.status})"


class LockerCredit(models.Model):
    """Prepaid balance for shop/cafe/recovery purchases."""
    member = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='locker_credit',
    )
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_cap = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'locker_credits'

    def __str__(self):
        return f"{self.member.email} — ${self.balance}"


class Invoice(models.Model):
    """Formal invoice record (PDF available on request)."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    invoice_number = models.CharField(max_length=30, unique=True)  # #INV-9921
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='invoices',
    )

    # References
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    # Details
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Dates
    issued_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'invoices'
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.invoice_number} — ${self.total} ({self.status})"