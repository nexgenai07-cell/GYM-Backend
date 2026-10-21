"""Services prices in riyals (were dollars) and Saudi phone placeholders. Admin-edited texts are kept."""
from django.db import migrations


def forward(apps, schema_editor):
    from apps.site_content.seeding import seed

    seed(apps.get_model('site_content', 'SiteText'), apps.get_model('site_content', 'SiteImage'))


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0006_facility_addon_texts'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
