from django.contrib import admin
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'category', 'title', 'is_read', 'created_at']
    list_filter = ['category', 'priority', 'is_read']
    search_fields = ['recipient__email', 'title']
    raw_id_fields = ['recipient']


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'push_enabled', 'email_enabled', 'whatsapp_enabled']
    search_fields = ['user__email']
    raw_id_fields = ['user']