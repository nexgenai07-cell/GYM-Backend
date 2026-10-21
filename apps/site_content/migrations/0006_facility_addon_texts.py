"""Texts for facility add-ons: the Facilities page Book button and the signup picker."""
from django.db import migrations


def forward(apps, schema_editor):
    from apps.site_content.seeding import seed
    seed(apps.get_model('site_content', 'SiteText'), apps.get_model('site_content', 'SiteImage'))


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0005_sync_site_texts'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
