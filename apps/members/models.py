from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date
import uuid


# ============================================================
# MEMBERSHIP PLANS
# ============================================================
class MembershipPlan(models.Model):
    """Available membership tiers. Edited by admin, displayed on public site."""
    TIER_CHOICES = [
        ('basic', 'Basic'),
        ('pro', 'Pro'),
        ('black', 'Black Elite'),
    ]

    name = models.CharField(max_length=50, choices=TIER_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2)
    price_annual = models.DecimalField(max_digits=8, decimal_places=2)
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'membership_plans'
        ordering = ['price_monthly']

    def __str__(self):
        return self.display_name


# ============================================================
# MEMBERSHIP
# ============================================================
class Membership(models.Model):
    """A member's active membership."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('frozen', 'Frozen'),
    ]

    member = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='membership',
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name='memberships',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateField()
    expiry_date = models.DateField()
    auto_renew = models.BooleanField(default=True)
    is_frozen = models.BooleanField(default=False)
    frozen_until = models.DateField(null=True, blank=True)

    # ⬇️ NEW — for gym entry lookup (Iqama = 10-digit Saudi residency ID)
    iqama_number = models.CharField(max_length=20, blank=True, db_index=True)

    # Digital pass
    pass_id = models.CharField(max_length=20, unique=True, blank=True)
    nfc_token = models.CharField(max_length=64, blank=True)

    # Stats
    lifetime_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_check_ins = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'memberships'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Auto-generate pass_id if missing — MUST run before super().save()
        if not self.pass_id:
            self.pass_id = f"TK-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member.email} — {self.plan.display_name}"

    @property
    def days_remaining(self):
        delta = self.expiry_date - date.today()
        return max(0, delta.days)


# ============================================================
# CHECK-IN
# ============================================================
class CheckIn(models.Model):
    """A single gym check-in record."""
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='check_ins',
    )
    facility = models.CharField(max_length=100, default='Metro Station Core 01')
    zone = models.CharField(max_length=100, blank=True)
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)

    # ⬇️ NEW — staff verification trail
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_check_ins',
    )
    face_verified = models.BooleanField(default=False)

    class Meta:
        db_table = 'check_ins'
        ordering = ['-check_in_time']

    def __str__(self):
        return f"{self.member.email} @ {self.check_in_time}"


# ============================================================
# MEMBERSHIP REGISTRATION (new — public signup pipeline)
# ============================================================
class MembershipRegistration(models.Model):
    """
    A pending public-site registration. Sits here until an admin approves it.
    On approval → creates a real User + Membership + Transaction.
    """
    STATUS_PENDING   = 'pending'
    STATUS_PAID      = 'payment_confirmed'
    STATUS_APPROVED  = 'approved'
    STATUS_REJECTED  = 'rejected'
    STATUS_EXPIRED   = 'expired'

    STATUS = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_PAID,     'Payment Confirmed'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_EXPIRED,  'Expired'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    # Applicant info
    iqama_number = models.CharField(max_length=20, unique=True, db_index=True)
    full_name    = models.CharField(max_length=150)
    email        = models.EmailField(unique=True)
    phone        = models.CharField(max_length=20)
    address      = models.TextField(blank=True)
    age          = models.IntegerField()
    gender       = models.CharField(max_length=20, choices=GENDER_CHOICES)
    photo        = models.ImageField(upload_to='registrations/%Y/%m/', blank=True, null=True)

    # Chosen plan
    plan            = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='registrations')
    duration_months = models.IntegerField(default=1)

    # Payment (Mada)
    payment_method    = models.CharField(max_length=20, default='mada')
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_amount    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status    = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_paid_at   = models.DateTimeField(null=True, blank=True)

    # Meta
    status           = models.CharField(max_length=30, choices=STATUS, default=STATUS_PENDING)
    submitted_at     = models.DateTimeField(auto_now_add=True)
    approved_at      = models.DateTimeField(null=True, blank=True)
    approved_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_registrations',
    )
    rejection_reason = models.TextField(blank=True)

    # Password (hashed — real User created only on approval)
    password_hash = models.CharField(max_length=255)

    # Link to created user (after approval)
    created_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='source_registration',
    )

    class Meta:
        db_table = 'membership_registrations'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"#{self.id} {self.full_name} — {self.get_status_display()}"

    @property
    def is_actionable(self):
        return self.status in (self.STATUS_PENDING, self.STATUS_PAID)

    @property
    def total_price(self):
        """Simple linear price: monthly * months (no annual discount logic here)."""
        if self.duration_months >= 12:
            # 12 months at annual rate
            years = self.duration_months / 12
            return round(float(self.plan.price_annual) * years, 2)
        return float(self.plan.price_monthly) * self.duration_months