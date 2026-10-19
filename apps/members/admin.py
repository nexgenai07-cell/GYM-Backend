from django.contrib import admin
from django.utils.html import format_html
from .models import MembershipPlan, Membership, CheckIn, MembershipRegistration, FaceCheck


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'price_monthly', 'price_annual', 'session_limit_minutes', 'is_active']
    list_filter = ['is_active', 'name']


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['member', 'plan', 'status', 'iqama_number', 'expiry_date', 'total_check_ins']
    list_filter = ['status', 'plan', 'is_frozen']
    search_fields = ['member__email', 'iqama_number', 'pass_id']
    raw_id_fields = ['member']


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ['member', 'facility', 'check_in_time', 'expected_checkout_time', 'check_out_time', 'duration_minutes', 'face_verified']
    list_filter = ['facility', 'face_verified']
    search_fields = ['member__email']
    raw_id_fields = ['member', 'verified_by']


@admin.register(FaceCheck)
class FaceCheckAdmin(admin.ModelAdmin):
    """Read-only security audit trail of gate face comparisons."""
    list_display = ['created_at', 'matched', 'iqama_number', 'member', 'confidence', 'threshold', 'verified_by', 'check_in']
    list_filter = ['matched', 'source']
    search_fields = ['iqama_number', 'member__email']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MembershipRegistration)
class MembershipRegistrationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'iqama_number', 'full_name', 'email',
        'plan', 'duration_months', 'payment_status', 'status',
        'submitted_at', 'photo_thumb',
    ]
    list_filter = ['status', 'payment_status', 'gender', 'plan']
    search_fields = ['iqama_number', 'full_name', 'email', 'phone', 'moyasar_payment_id']
    readonly_fields = [
        'password_hash', 'submitted_at', 'approved_at',
        'approved_by', 'created_user', 'photo_preview',
        # Payment fields are only ever set by Moyasar verification — never by hand.
        'payment_method', 'payment_reference', 'payment_amount', 'payment_status',
        'payment_paid_at', 'moyasar_payment_id', 'payment_attempt_token',
        'payment_failure_reason', 'payment_raw',
    ]
    raw_id_fields = ['plan', 'created_user', 'approved_by']
    actions = ['action_approve_selected', 'action_reject_selected']

    def photo_thumb(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="height:36px;border-radius:4px;" />',
                obj.photo.url,
            )
        return '—'
    photo_thumb.short_description = 'Photo'

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height:240px;border-radius:8px;" />',
                obj.photo.url,
            )
        return '—'
    photo_preview.short_description = 'Photo preview'

    @admin.action(description='✅ Approve selected registrations')
    def action_approve_selected(self, request, queryset):
        from .services import approve_registration
        ok, fail = 0, []
        for reg in queryset:
            try:
                approve_registration(reg, approved_by=request.user)
                ok += 1
            except Exception as e:
                fail.append((reg.id, str(e)))
        self.message_user(request, f'Approved {ok}. Failed {len(fail)}: {fail}')

    @admin.action(description='❌ Reject selected registrations')
    def action_reject_selected(self, request, queryset):
        from .services import reject_registration
        for reg in queryset:
            try:
                reject_registration(reg, reason='Rejected via admin bulk action.', rejected_by=request.user)
            except Exception:
                pass
        self.message_user(request, f'Rejected {queryset.count()}.')