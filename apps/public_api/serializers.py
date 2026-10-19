import re
import secrets
from decimal import Decimal

from rest_framework import serializers
from django.contrib.auth.hashers import make_password

from apps.members.models import (
    MembershipPlan, MembershipRegistration, Membership,
)
from .moyasar import sync_payment, MoyasarError, MoyasarUnavailable

IQAMA_RE = re.compile(r'^2\d{9}$')          # Saudi residency ID: 10 digits, starts with 2
MAX_PHOTO_BYTES = 4 * 1024 * 1024           # Vercel rejects request bodies over 4.5 MB


def plan_amount(plan, months):
    """Server-side price in SAR — the browser never decides how much to charge."""
    if months >= 12:
        return (Decimal(plan.price_annual) * months / 12).quantize(Decimal('0.01'))
    return (Decimal(plan.price_monthly) * months).quantize(Decimal('0.01'))


# ============================================================
# PUBLIC — READ
# ============================================================
class PublicPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = [
            'id', 'name', 'display_name', 'description',
            'price_monthly', 'price_annual', 'features', 'session_limit_minutes',
        ]


# ============================================================
# PUBLIC — REGISTER
# ============================================================
class RegistrationCreateSerializer(serializers.ModelSerializer):
    """
    Accepts multipart/form-data from the public site:
      iqama_number, full_name, email, phone, address, age, gender,
      photo (file, required), plan (id), duration_months

    No password: the login password is generated and emailed on approval
    (apps.members.services). A `password` field, if sent, is ignored.

    Resubmitting with the same Iqama + email as an existing *unpaid* pending
    registration (e.g. after a declined card) updates it instead of failing.
    """
    plan = serializers.PrimaryKeyRelatedField(
        queryset=MembershipPlan.objects.filter(is_active=True),
    )
    # Declared explicitly so DRF doesn't add UniqueValidators; validate() handles duplicates.
    iqama_number = serializers.CharField(max_length=20)
    email = serializers.EmailField(max_length=254)
    photo = serializers.ImageField()

    class Meta:
        model = MembershipRegistration
        fields = [
            'iqama_number', 'full_name', 'email', 'phone',
            'address', 'age', 'gender', 'photo',
            'plan', 'duration_months',
        ]

    def validate_iqama_number(self, value):
        value = value.strip()
        if not IQAMA_RE.match(value):
            raise serializers.ValidationError('Iqama number must be 10 digits starting with 2.')
        return value

    def validate_email(self, value):
        return value.strip().lower()

    def validate_photo(self, value):
        if value.size > MAX_PHOTO_BYTES:
            raise serializers.ValidationError('Photo must be under 4 MB.')
        return value

    def validate(self, attrs):
        by_iqama = MembershipRegistration.objects.filter(iqama_number=attrs['iqama_number']).first()
        by_email = MembershipRegistration.objects.filter(email__iexact=attrs['email']).first()
        existing = by_iqama or by_email
        if existing is None:
            return attrs

        resumable = (
            by_iqama == by_email
            and existing.status == MembershipRegistration.STATUS_PENDING
            and existing.payment_status != 'paid'
        )
        if resumable and existing.moyasar_payment_id:
            # Make sure the last attempt didn't succeed while the user was away.
            try:
                existing = sync_payment(existing.moyasar_payment_id)
            except MoyasarUnavailable:
                # Can't rule out that the last attempt succeeded — don't discard it.
                raise serializers.ValidationError(
                    {'detail': 'Could not check your previous payment. Please try again shortly.'}
                )
            except MoyasarError:
                pass
            resumable = (
                existing.status == MembershipRegistration.STATUS_PENDING
                and existing.payment_status != 'paid'
            )

        if not resumable:
            errors = {}
            if by_iqama:
                errors['iqama_number'] = 'This Iqama number is already registered.'
            if by_email:
                errors['email'] = 'This email is already registered.'
            raise serializers.ValidationError(errors)

        self._resume = existing
        return attrs

    def validate_duration_months(self, value):
        if value < 1 or value > 24:
            raise serializers.ValidationError('Duration must be between 1 and 24 months.')
        return value

    def create(self, validated_data):
        # The real password is generated on approval; keep the column non-empty but unusable.
        validated_data['password_hash'] = make_password(None)
        validated_data['payment_amount'] = plan_amount(
            validated_data['plan'], validated_data.get('duration_months', 1),
        )
        validated_data['payment_status'] = 'pending'
        validated_data['payment_failure_reason'] = ''
        validated_data['payment_attempt_token'] = secrets.token_urlsafe(24)  # new attempt
        validated_data['status'] = MembershipRegistration.STATUS_PENDING

        reg = getattr(self, '_resume', None)
        if reg is None:
            return MembershipRegistration.objects.create(**validated_data)

        # Retry of an unpaid registration: overwrite it and start a fresh payment.
        old_photo = reg.photo.name if reg.photo else None
        for field, value in validated_data.items():
            setattr(reg, field, value)
        reg.moyasar_payment_id = None
        reg.save()
        if old_photo and old_photo != reg.photo.name:
            reg.photo.storage.delete(old_photo)
        return reg


class RegistrationStatusSerializer(serializers.ModelSerializer):
    """
    Public, unauthenticated view (anyone can call it with any id), so it
    carries no personal data — only processing state.
    """
    class Meta:
        model = MembershipRegistration
        fields = ['id', 'status', 'payment_status', 'payment_failure_reason']


# ============================================================
# ADMIN — READ / MANAGE
# ============================================================
class AdminRegistrationSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.display_name', read_only=True)
    photo_url = serializers.SerializerMethodField()
    approved_by_email = serializers.EmailField(source='approved_by.email', read_only=True, allow_null=True)
    created_user_email = serializers.EmailField(source='created_user.email', read_only=True, allow_null=True)

    class Meta:
        model = MembershipRegistration
        fields = [
            'id',
            'iqama_number', 'full_name', 'email', 'phone',
            'address', 'age', 'gender', 'photo_url',
            'plan', 'plan_name', 'duration_months',
            'payment_method', 'payment_reference', 'payment_amount',
            'payment_status', 'payment_paid_at',
            'moyasar_payment_id', 'payment_failure_reason',
            'status', 'submitted_at', 'approved_at',
            'approved_by_email', 'rejection_reason',
            'created_user_email',
        ]

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        request = self.context.get('request')
        url = obj.photo.url
        return request.build_absolute_uri(url) if request else url


class BulkApproveSerializer(serializers.Serializer):
    """Body for POST /api/admin/registrations/bulk-approve/"""
    ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text='Optional list of IDs. If omitted, approves all pending.',
    )
    only_today = serializers.BooleanField(
        default=False,
        help_text='If true, restricts to registrations submitted today.',
    )


class PaymentIdSerializer(serializers.Serializer):
    """Body for the attach / verify endpoints: the Moyasar payment id."""
    payment_id = serializers.CharField(max_length=64)


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')