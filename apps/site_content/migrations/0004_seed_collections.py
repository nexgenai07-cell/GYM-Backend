"""
Facilities and Insights articles become admin-managed lists (SiteItem):
create them from what the site shipped with, and drop the per-card text/image
slots 0002 created for them, so each value is edited in exactly one place.
"""
from django.db import migrations

MOVED_TEXT_PATTERN = r'^(fac\.c[0-9]+\.|ins\.art[0-9]+\.)'
MOVED_IMAGES = [
    'fac.pool', 'fac.basketball', 'fac.combat', 'fac.recovery', 'fac.volleyball', 'fac.strength',
    'ins.vo2', 'ins.nutrition', 'ins.cryo', 'ins.grip', 'ins.squat',
]


def forward(apps, schema_editor):
    from apps.site_content.seeding import seed_collections
    seed_collections(apps.get_model('site_content', 'SiteItem'))
    apps.get_model('site_content', 'SiteText').objects.filter(key__regex=MOVED_TEXT_PATTERN).delete()
    apps.get_model('site_content', 'SiteImage').objects.filter(key__in=MOVED_IMAGES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0003_site_item'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
