"""
Every product SKU follows the fixed format: the category's 3-letter prefix, a dash and 4 digits
(PRO-0001). SKUs that don't are given the next free number in their category. Past orders keep
the SKU they were sold under (order_items.product_sku is a copy).
"""
import re

from django.db import migrations

SKU_RE = re.compile(r'[A-Z]{3}-\d{4}')


def prefix(category):
    return (re.sub(r'[^A-Za-z]', '', category.key or category.name).upper() + 'XXX')[:3]


def forward(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    products = list(Product.objects.select_related('category').order_by('id'))
    taken = {(p.sku or '').upper() for p in products}     # every current SKU, so a new one never collides
    for p in products:
        pre = prefix(p.category)
        if SKU_RE.fullmatch(p.sku or '') and p.sku.startswith(pre + '-'):
            continue
        n = 1
        while f'{pre}-{n:04d}' in taken:
            n += 1
        p.sku = f'{pre}-{n:04d}'
        taken.add(p.sku)
        p.save(update_fields=['sku'])


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
