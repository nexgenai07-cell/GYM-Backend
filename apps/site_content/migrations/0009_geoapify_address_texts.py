"""Geoapify address hints (Google map texts dropped) and the +966 phone placeholders. Admin-edited texts are kept."""
from django.db import migrations

REMOVED = ['en.map.search', 'en.map.mine', 'en.map.locating', 'en.map.label']


def forward(apps, schema_editor):
    from apps.site_content.seeding import seed

    SiteText = apps.get_model('site_content', 'SiteText')
    seed(SiteText, apps.get_model('site_content', 'SiteImage'))
    SiteText.objects.filter(key__in=REMOVED).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0008_signup_map_and_facility_texts'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
