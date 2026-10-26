from django.db import models
from django.conf import settings


class SystemSettings(models.Model):
    """
    Singleton model — always use pk=1.
    Stores all admin-configurable settings as JSON.
    """
    general = models.JSONField(default=dict, blank=True)
    roles = models.JSONField(default=dict, blank=True)
    integrations = models.JSONField(default=dict, blank=True)
    security = models.JSONField(default=dict, blank=True)
    notifications = models.JSONField(default=dict, blank=True)
    billing = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        db_table = 'system_settings'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return 'System Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

class AdminSeen(models.Model):
    """When an admin last opened a sidebar section — new activity after this shows as a badge."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_seen')
    section = models.CharField(max_length=40)
    seen_at = models.DateTimeField()

    class Meta:
        db_table = 'admin_seen'
        unique_together = ('user', 'section')
