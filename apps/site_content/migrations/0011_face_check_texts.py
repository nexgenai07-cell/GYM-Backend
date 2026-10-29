"""
Camera texts for the signup face check (no face, two faces, too far, cut off, turned, tilted,
backlit, blurry, checker unavailable, face detected). Admin-edited texts are kept.
"""
from django.db import migrations


def forward(apps, schema_editor):
    from apps.site_content.seeding import seed

    seed(apps.get_model('site_content', 'SiteText'), apps.get_model('site_content', 'SiteImage'))


class Migration(migrations.Migration):

    dependencies = [
        ('site_content', '0010_clearer_signup_errors'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
