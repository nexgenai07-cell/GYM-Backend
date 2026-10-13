from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'full_name_display', 'role', 'is_verified', 'is_active', 'created_at']
    list_filter = ['role', 'is_verified', 'is_active', 'is_staff']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone']
    ordering = ['-created_at']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Smart Gym Profile', {
            'fields': ('role', 'phone', 'avatar', 'date_of_birth', 'is_verified')
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Smart Gym Profile', {
            'fields': ('email', 'role', 'phone'),
        }),
    )

    def full_name_display(self, obj):
        return obj.full_name
    full_name_display.short_description = 'Full Name'