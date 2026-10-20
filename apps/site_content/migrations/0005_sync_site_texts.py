"""
Bring the text/image slots in line with the rewired public site (Phase 3):
add the new texts (prices, stats, contact numbers, article/404/payment/camera
pages) and drop the slots the site no longer shows (sample articles, home
sectors now taken from the Facilities list, simulated live numbers, booking).
"""
import json

from django.db import migrations


def forward(apps, schema_editor):
    from apps.site_content.seeding import SEED_DIR, seed

    SiteText = apps.get_model('site_content', 'SiteText')
    SiteImage = apps.get_model('site_content', 'SiteImage')
    seed(SiteText, SiteImage)
    text_keys = {row['key'] for row in json.loads((SEED_DIR / 'texts.json').read_text(encoding='utf-8'))}
    image_keys = {row['key'] for row in json.loads((SEED_DIR / 'images.json').read_text(encoding='utf-8'))}
    SiteText.objects.exclude(key__in=text_keys).delete()
    SiteImage.objects.exclude(key__in=image_keys).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0004_seed_collections'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
