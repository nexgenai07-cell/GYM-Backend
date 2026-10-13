# apps/members/serializers.py
from rest_framework import serializers
from .models import MembershipPlan, Membership, CheckIn


class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = [
            'id', 'name', 'display_name', 'description',
            'price_monthly', 'price_annual', 'features', 'is_active',
        ]


class MembershipSerializer(serializers.ModelSerializer):
    plan = MembershipPlanSerializer(read_only=True)
    member_name = serializers.SerializerMethodField()
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Membership
        fields = [
            'id', 'plan', 'status', 'start_date', 'expiry_date',
            'auto_renew', 'is_frozen', 'frozen_until',
            'pass_id', 'nfc_token',
            'lifetime_value', 'total_check_ins',
            'days_remaining', 'member_name',
            'created_at', 'updated_at',
        ]

    def get_member_name(self, obj):
        u = obj.member
        # Try full_name property, fallback to first+last, fallback to email
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        return name or u.email


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = [
            'id', 'facility', 'zone',
            'check_in_time', 'check_out_time', 'duration_minutes',
        ]
        read_only_fields = ['id', 'check_in_time']