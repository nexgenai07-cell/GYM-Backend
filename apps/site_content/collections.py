"""
Admin-managed lists on the public site ("collections"): facilities, articles, …

Each collection is a schema of fields; items store their values in SiteItem.data:
  i18n text  → {"en": "...", "ar": "..."}
  everything else → a plain value
The same schema drives validation here, the admin portal's form, and the
public API. Adding a list = adding a schema (no migration).
"""
import datetime
import re

from django.utils.text import slugify

TEXT, TEXTAREA, CHOICE, INT, DATE = 'text', 'textarea', 'choice', 'int', 'date'


def f(name, label, type_=TEXT, i18n=False, required=False, choices=None, max_length=None):
    return {'name': name, 'label': label, 'type': type_, 'i18n': i18n, 'required': required,
            'choices': choices or [], 'max_length': max_length or (20000 if type_ == TEXTAREA else 300)}


COLLECTIONS = {
    'facilities': {
        'label': 'Facilities',
        'page': 'fac',
        'has_image': True,
        'has_slug': False,
        'fields': [
            f('title', 'Name', i18n=True, required=True),
            f('category', 'Category (page filter)', CHOICE, required=True,
              choices=['aquatics', 'courts', 'combat', 'recovery', 'strength']),
            f('sector', 'Sector label', i18n=True),
            f('location', 'Location', i18n=True),
            f('tag', 'Tag line', i18n=True),
            f('status', 'Status text', i18n=True),
            f('status_tone', 'Status colour', CHOICE, choices=['ok', 'busy', 'closed']),
            f('description', 'Description', TEXTAREA, i18n=True),
            f('stat1_label', 'Stat 1 label', i18n=True), f('stat1_value', 'Stat 1 value'),
            f('stat2_label', 'Stat 2 label', i18n=True), f('stat2_value', 'Stat 2 value'),
            f('stat3_label', 'Stat 3 label', i18n=True), f('stat3_value', 'Stat 3 value'),
        ],
    },
    'articles': {
        'label': 'Insights articles',
        'page': 'ins',
        'has_image': True,
        'has_slug': True,
        'fields': [
            f('title', 'Title', i18n=True, required=True),
            f('category', 'Category (page filter)', CHOICE, required=True,
              choices=['training', 'nutrition', 'recovery', 'biometrics', 'case-studies']),
            f('tag', 'Tag line', i18n=True),
            f('published', 'Publish date', DATE, required=True),
            f('read_minutes', 'Reading time (minutes)', INT),
            f('excerpt', 'Summary (card)', TEXTAREA, i18n=True),
            f('body', 'Full article', TEXTAREA, i18n=True),
            f('author', 'Author'),
            f('author_line', 'Author line / team', i18n=True),
        ],
    },
}


def schema_for(name):
    return COLLECTIONS.get(name)


class CollectionError(ValueError):
    def __init__(self, errors):
        super().__init__(str(errors))
        self.errors = errors


def clean_data(collection, data, partial=False, existing=None):
    """
    Validate item data against the collection schema. Returns the full cleaned
    dict (merged over `existing` when partial). Raises CollectionError({field: msg}).
    """
    schema = COLLECTIONS[collection]
    fields = {fd['name']: fd for fd in schema['fields']}
    if not isinstance(data, dict):
        raise CollectionError({'data': 'Must be an object.'})
    unknown = set(data) - set(fields)
    errors = {name: 'Unknown field.' for name in unknown}
    out = dict(existing or {})

    for name, fd in fields.items():
        if name not in data:
            if not partial and name not in out:
                out[name] = {'en': '', 'ar': ''} if fd['i18n'] else ('' if fd['type'] != INT else None)
            continue
        value = data[name]
        try:
            out[name] = _clean_value(fd, value)
        except ValueError as exc:
            errors[name] = str(exc)

    for name, fd in fields.items():
        if fd['required'] and name not in errors:
            v = out.get(name)
            if (fd['i18n'] and not (v or {}).get('en', '').strip()) or (not fd['i18n'] and v in ('', None)):
                errors[name] = 'Required' + (' (English at least).' if fd['i18n'] else '.')
    if errors:
        raise CollectionError(errors)
    return out


def _clean_value(fd, value):
    if fd['i18n']:
        if not isinstance(value, dict) or set(value) - {'en', 'ar'}:
            raise ValueError('Expected {"en": ..., "ar": ...}.')
        cleaned = {}
        for lang in ('en', 'ar'):
            v = value.get(lang, '')
            if not isinstance(v, str):
                raise ValueError(f'{lang} must be text.')
            if len(v) > fd['max_length']:
                raise ValueError(f'{lang} is longer than {fd["max_length"]} characters.')
            cleaned[lang] = v.strip()
        return cleaned
    if fd['type'] == CHOICE:
        if value in ('', None) and not fd['required']:
            return ''
        if value not in fd['choices']:
            raise ValueError(f'Choose one of: {", ".join(fd["choices"])}.')
        return value
    if fd['type'] == INT:
        if value in ('', None):
            return None
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise ValueError('Must be a whole number.')
        if n < 0 or n > 100000:
            raise ValueError('Out of range.')
        return n
    if fd['type'] == DATE:
        if value in ('', None):
            return ''
        try:
            return datetime.date.fromisoformat(str(value)).isoformat()
        except ValueError:
            raise ValueError('Use YYYY-MM-DD.')
    if not isinstance(value, (str, int, float)):
        raise ValueError('Must be text.')
    value = str(value).strip()
    if len(value) > fd['max_length']:
        raise ValueError(f'Longer than {fd["max_length"]} characters.')
    return value


def make_slug(SiteItem, collection, data, exclude_pk=None):
    """Unique per collection, from the English title."""
    base = slugify((data.get('title') or {}).get('en', '')) or 'item'
    base = re.sub(r'-+', '-', base)[:80].strip('-') or 'item'
    slug, n = base, 2
    qs = SiteItem.objects.filter(collection=collection)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        slug, n = f'{base}-{n}', n + 1
    return slug
