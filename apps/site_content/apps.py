from django.apps import AppConfig


class SiteContentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.site_content'
    verbose_name = 'Public site content'
