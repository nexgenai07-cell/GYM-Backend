"""
Clearer signup field error messages (shown under each field now) and home-page labels that now
sit next to real, live numbers. Admin-edited texts are kept.
"""
from django.db import migrations


def forward(apps, schema_editor):
    from apps.site_content.seeding import seed

    seed(apps.get_model('site_content', 'SiteText'), apps.get_model('site_content', 'SiteImage'))


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0009_geoapify_address_texts'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
