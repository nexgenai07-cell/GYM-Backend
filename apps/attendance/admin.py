from django.contrib import admin
from .models import Milestone, MemberMilestone


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ['tier', 'title', 'tier_type', 'target_days', 'is_active']
    list_filter = ['tier_type', 'is_active']
    ordering = ['display_order']


@admin.register(MemberMilestone)
class MemberMilestoneAdmin(admin.ModelAdmin):
    list_display = ['member', 'milestone', 'status', 'progress', 'current_days', 'claimed_at']
    list_filter = ['status', 'milestone']
    raw_id_fields = ['member', 'milestone']