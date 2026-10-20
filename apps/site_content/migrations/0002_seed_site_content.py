"""Pre-fill every public-site text (en/ar) and image slot with what the site shipped with."""
from django.db import migrations


def seed_forward(apps, schema_editor):
    from apps.site_content.seeding import seed
    seed(apps.get_model('site_content', 'SiteText'), apps.get_model('site_content', 'SiteImage'))


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0001_initial'),
    ]

    operations = [
        # Reverse is a no-op: 0001's reverse drops the tables anyway.
        migrations.RunPython(seed_forward, migrations.RunPython.noop),
    ]
