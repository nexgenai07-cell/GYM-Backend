from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.members.models import (
    MembershipPlan, MembershipRegistration, Membership,
)


# ============================================================
# PUBLIC — READ
# ============================================================
class PublicPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = [
            'id', 'name', 'display_name', 'description',
            'price_monthly', 'price_annual', 'features',
        ]


# ============================================================
# PUBLIC — REGISTER
# ============================================================
class RegistrationCreateSerializer(serializers.ModelSerializer):
    """
    Accepts multipart/form-data from the public site:
      iqama_number, full_name, email, phone, address, age, gender,
      photo (file), plan (id), duration_months, password
    """
    plan = serializers.PrimaryKeyRelatedField(
        queryset=MembershipPlan.objects.filter(is_active=True),
    )
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = MembershipRegistration
        fields = [
            'iqama_number', 'full_name', 'email', 'phone',
            'address', 'age', 'gender', 'photo',
            'plan', 'duration_months', 'password',
        ]

    def validate_iqama_number(self, value):
        value = value.strip().upper()
        if MembershipRegistration.objects.filter(iqama_number__iexact=value).exists():
            raise serializers.ValidationError('This Iqama number is already registered.')
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if MembershipRegistration.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('This email is already registered.')
        return value

    def validate_duration_months(self, value):
        if value < 1 or value > 24:
            raise serializers.ValidationError('Duration must be between 1 and 24 months.')
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        # Hash password now; store in password_hash. Real User only on approval.
        from django.contrib.auth.hashers import make_password
        password_hash = make_password(password)

        plan = validated_data['plan']
        months = validated_data.get('duration_months', 1)

        # Compute expected amount
        if months >= 12:
            years = months / 12
            amount = round(float(plan.price_annual) * years, 2)
        else:
            amount = float(plan.price_monthly) * months

        reg = MembershipRegistration.objects.create(
            **validated_data,
            password_hash=password_hash,
            payment_amount=amount,
            payment_status='pending',
            status=MembershipRegistration.STATUS_PENDING,
        )
        return reg


class RegistrationStatusSerializer(serializers.ModelSerializer):
    """Public-safe view — no password, no internal IDs."""
    plan_name = serializers.CharField(source='plan.display_name', read_only=True)

    class Meta:
        model = MembershipRegistration
        fields = [
            'id', 'iqama_number', 'full_name', 'email',
            'plan_name', 'duration_months',
            'payment_amount', 'payment_status',
            'status', 'submitted_at', 'approved_at',
            'rejection_reason',
        ]


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


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')