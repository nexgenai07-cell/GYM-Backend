"""Signup texts: Saudi mobile hint, facility add/remove + months, address map. Admin-edited texts are kept."""
from django.db import migrations


def forward(apps, schema_editor):
    from apps.site_content.seeding import seed

    seed(apps.get_model('site_content', 'SiteText'), apps.get_model('site_content', 'SiteImage'))


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0007_sar_service_prices'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
