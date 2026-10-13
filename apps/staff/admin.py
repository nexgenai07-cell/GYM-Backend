from django.contrib import admin
from .models import StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'status', 'permissions_count', 'created_at']
    list_filter = ['department', 'status']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user']