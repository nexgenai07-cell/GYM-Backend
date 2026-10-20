"""
Seed site texts and image slots from seed/texts.json and seed/images.json
(exported from the public site's src/i18n/strings.js and its IMG constants).

Safe to run repeatedly: new slots are added; for existing slots the shipped
defaults are refreshed, and the live value follows them only if an admin
hasn't customised it. Admin edits are never overwritten.
"""
import json
from pathlib import Path

from .models import PAGES

SEED_DIR = Path(__file__).resolve().parent / 'seed'


def _image_label(key, page):
    rest = key.split('.', 1)[1] if '.' in key else key
    return f"{PAGES.get(page, page)} — {rest.replace('.', ' ').replace('_', ' ')}"


def seed(SiteText, SiteImage):
    """Takes the model classes so a data migration can pass historical models."""
    texts = json.loads((SEED_DIR / 'texts.json').read_text(encoding='utf-8'))
    images = json.loads((SEED_DIR / 'images.json').read_text(encoding='utf-8'))
    stats = {'texts_added': 0, 'texts_refreshed': 0, 'images_added': 0, 'images_refreshed': 0}

    existing = {t.key: t for t in SiteText.objects.all()}
    new_rows = []
    for row in texts:
        obj = existing.get(row['key'])
        if obj is None:
            new_rows.append(SiteText(key=row['key'], page=row['page'], en=row['en'], ar=row['ar'],
                                     default_en=row['en'], default_ar=row['ar']))
            continue
        if (obj.default_en, obj.default_ar) == (row['en'], row['ar']):
            continue
        untouched = (obj.en, obj.ar) == (obj.default_en, obj.default_ar)
        obj.default_en, obj.default_ar = row['en'], row['ar']
        if untouched:
            obj.en, obj.ar = row['en'], row['ar']
        obj.save(update_fields=['default_en', 'default_ar', 'en', 'ar'])
        stats['texts_refreshed'] += 1
    SiteText.objects.bulk_create(new_rows, batch_size=500)
    stats['texts_added'] = len(new_rows)

    existing = {i.key: i for i in SiteImage.objects.all()}
    for row in images:
        obj = existing.get(row['key'])
        if obj is None:
            SiteImage.objects.create(key=row['key'], page=row['page'],
                                     label=_image_label(row['key'], row['page']),
                                     default_url=row['default_url'])
            stats['images_added'] += 1
        elif obj.default_url != row['default_url']:
            obj.default_url = row['default_url']
            obj.save(update_fields=['default_url'])
            stats['images_refreshed'] += 1
    return stats
