from rest_framework import serializers
from .models import ReportTemplate, GeneratedReport


class ReportTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportTemplate
        fields = [
            'id', 'key', 'title', 'description', 'icon',
            'frequency', 'is_active', 'is_featured',
        ]


class GeneratedReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'report_id', 'name', 'report_type', 'period', 'format',
            'size_kb', 'row_count', 'period_start', 'period_end', 'generated_at',
            'generated_by_name', 'time_ago',
        ]

    def get_generated_by_name(self, obj):
        if not obj.generated_by:
            return 'System'
        u = obj.generated_by
        # Try full_name property first, then first+last, then email
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        return name or u.email

    def get_time_ago(self, obj):
        from django.utils import timezone
        delta = timezone.now() - obj.generated_at
        seconds = int(delta.total_seconds())

        if seconds < 60:
            return 'Just now'
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min ago" if minutes > 1 else "1 min ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        days = hours // 24
        if days < 30:
            return f"{days} day{'s' if days > 1 else ''} ago"
        return obj.generated_at.strftime('%b %d, %Y')