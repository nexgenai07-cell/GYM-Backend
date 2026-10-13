from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'category', 'priority', 'icon', 'title', 'message',
            'action_label', 'action_path', 'is_read', 'read_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'read_at']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'push_enabled', 'email_enabled', 'whatsapp_enabled',
            'sms_enabled', 'marketing_enabled',
        ]