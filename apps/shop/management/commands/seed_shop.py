from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.shop.models import ProductCategory, Product, PromoCode


CATEGORIES = [
    {'key': 'protein', 'name': 'Protein', 'icon': 'fitness_center', 'display_order': 1},
    {'key': 'pre-workout', 'name': 'Pre-Workout', 'icon': 'bolt', 'display_order': 2},
    {'key': 'recovery', 'name': 'Recovery', 'icon': 'healing', 'display_order': 3},
    {'key': 'gear', 'name': 'Gear', 'icon': 'sports_gymnastics', 'display_order': 4},
    {'key': 'apparel', 'name': 'Apparel', 'icon': 'checkroom', 'display_order': 5},
]

PRODUCTS = [
    # PROTEIN
    {
        'sku': 'WHEY-ISO-01',
        'name': 'Titan Whey Isolate',
        'category_key': 'protein',
        'description': 'Cold-filtered whey isolate — 28g protein, 6.8g BCAA per scoop. Zero fillers.',
        'image_url': 'https://images.unsplash.com/photo-1593095948071-474c5cc2989d?w=800',
        'price': Decimal('64.99'),
        'original_price': Decimal('79.99'),
        'price_note': 'Pro Member Price',
        'badge_top': 'Pro Perk 15% Off',
        'badge_top_accent': True,
        'badge_secondary': 'Cold-Filtered',
        'telemetry': ['28G PROTEIN / SRV', '6.8G BCAA'],
        'stock_quantity': 42,
        'stock_label': 'In Stock (42 Tubs)',
        'rating': Decimal('4.80'),
        'total_reviews': 218,
        'is_featured': True,
    },
    {
        'sku': 'WHEY-CONC-02',
        'name': 'Titan Whey Concentrate',
        'category_key': 'protein',
        'description': 'Classic whey concentrate — rich in immunoglobulins, ideal post-workout.',
        'image_url': 'https://images.unsplash.com/photo-1579722821273-0f6c1b5d0b8f?w=800',
        'price': Decimal('44.99'),
        'price_note': 'Standard Price',
        'telemetry': ['24G PROTEIN / SRV', '5G BCAA'],
        'stock_quantity': 25,
        'stock_label': 'In Stock (25 Tubs)',
        'rating': Decimal('4.50'),
        'total_reviews': 142,
    },
    {
        'sku': 'VEGAN-PRO-03',
        'name': 'Titan Plant Protein',
        'category_key': 'protein',
        'description': 'Pea + rice protein blend — complete amino profile, easy digestion.',
        'image_url': 'https://images.unsplash.com/photo-1622484212850-eb596d769edc?w=800',
        'price': Decimal('54.99'),
        'price_note': 'Vegan Formula',
        'telemetry': ['25G PROTEIN / SRV', 'Zero Dairy'],
        'stock_quantity': 3,
        'stock_label': 'Low Stock (3 Tubs)',
        'low_stock_threshold': 5,
        'rating': Decimal('4.60'),
        'total_reviews': 89,
    },

    # PRE-WORKOUT
    {
        'sku': 'PRE-IGN-01',
        'name': 'Ignite Pre-Workout',
        'category_key': 'pre-workout',
        'description': 'Explosive energy — 300mg caffeine, citrulline, beta-alanine.',
        'image_url': 'https://images.unsplash.com/photo-1594737625785-a6cbdabd333c?w=800',
        'price': Decimal('39.99'),
        'price_note': 'Alpha Series',
        'badge_top': 'Bestseller',
        'badge_top_accent': True,
        'telemetry': ['300MG CAFFEINE', '6G CITRULLINE'],
        'stock_quantity': 60,
        'stock_label': 'In Stock (60 Jars)',
        'rating': Decimal('4.90'),
        'total_reviews': 312,
        'is_featured': True,
    },
    {
        'sku': 'PRE-FOCUS-02',
        'name': 'Focus Nootropic Pre',
        'category_key': 'pre-workout',
        'description': 'Caffeine-free nootropic blend — for late-night training.',
        'image_url': 'https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=800',
        'price': Decimal('44.99'),
        'price_note': 'Caffeine-Free',
        'telemetry': ['NO CAFFEINE', 'L-THEANINE'],
        'stock_quantity': 18,
        'stock_label': 'In Stock (18 Jars)',
        'rating': Decimal('4.40'),
        'total_reviews': 67,
    },

    # RECOVERY
    {
        'sku': 'REC-BCAA-01',
        'name': 'Titan BCAA Recovery',
        'category_key': 'recovery',
        'description': '2:1:1 BCAA ratio with electrolytes — intra-workout hydration.',
        'image_url': 'https://images.unsplash.com/photo-1610725664285-7c57e6eeac3f?w=800',
        'price': Decimal('34.99'),
        'telemetry': ['7G BCAA', 'Electrolytes'],
        'stock_quantity': 30,
        'stock_label': 'In Stock (30 Tubs)',
        'rating': Decimal('4.50'),
        'total_reviews': 121,
    },
    {
        'sku': 'REC-CREA-02',
        'name': 'Creatine Monohydrate',
        'category_key': 'recovery',
        'description': 'Pure micronized creatine — 5g per serving, 100 servings per tub.',
        'image_url': 'https://images.unsplash.com/photo-1593095948071-474c5cc2989d?w=800',
        'price': Decimal('24.99'),
        'original_price': Decimal('29.99'),
        'price_note': 'Save 17%',
        'telemetry': ['5G CREATINE', '100 SRV'],
        'stock_quantity': 100,
        'stock_label': 'In Stock (100 Tubs)',
        'rating': Decimal('4.90'),
        'total_reviews': 456,
        'is_featured': True,
    },

    # GEAR
    {
        'sku': 'GEAR-BELT-01',
        'name': 'Titan Lifting Belt',
        'category_key': 'gear',
        'description': '10mm leather powerlifting belt with quick-release lever.',
        'image_url': 'https://images.unsplash.com/photo-1517344884509-a0c97ec11bcc?w=800',
        'price': Decimal('89.99'),
        'telemetry': ['10MM LEATHER', 'IPF APPROVED'],
        'stock_quantity': 12,
        'stock_label': 'In Stock (12 Belts)',
        'rating': Decimal('4.70'),
        'total_reviews': 88,
    },
    {
        'sku': 'GEAR-STRAP-02',
        'name': 'Titan Lifting Straps',
        'category_key': 'gear',
        'description': 'Heavy-duty cotton straps — reinforced stitching, no-slip grip.',
        'image_url': 'https://images.unsplash.com/photo-1591940742878-13aba4b7a34e?w=800',
        'price': Decimal('19.99'),
        'telemetry': ['HEAVY DUTY', 'COTTON'],
        'stock_quantity': 45,
        'stock_label': 'In Stock (45 Pairs)',
        'rating': Decimal('4.50'),
        'total_reviews': 132,
    },

    # APPAREL
    {
        'sku': 'APP-TEE-01',
        'name': 'Titan Training Tee',
        'category_key': 'apparel',
        'description': 'Moisture-wicking training tee — anti-odor technology.',
        'image_url': 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800',
        'price': Decimal('34.99'),
        'telemetry': ['MOISTURE WICK', 'ANTI-ODOR'],
        'stock_quantity': 80,
        'stock_label': 'In Stock (80 Units)',
        'rating': Decimal('4.60'),
        'total_reviews': 201,
    },
]


class Command(BaseCommand):
    help = 'Seed shop categories + products + promo codes'

    def handle(self, *args, **options):
        # ---- Categories ----
        cat_map = {}
        for c in CATEGORIES:
            cat, _ = ProductCategory.objects.update_or_create(
                key=c['key'],
                defaults={
                    'name': c['name'],
                    'icon': c.get('icon', ''),
                    'display_order': c.get('display_order', 0),
                    'is_active': True,
                },
            )
            cat_map[c['key']] = cat
            self.stdout.write(self.style.SUCCESS(f"  ✓ Category: {cat.name}"))

        # ---- Products ----
        for p in PRODUCTS:
            cat = cat_map[p['category_key']]
            Product.objects.update_or_create(
                sku=p['sku'],
                defaults={
                    'category': cat,
                    'name': p['name'],
                    'description': p.get('description', ''),
                    'image_url': p.get('image_url', ''),
                    'price': p['price'],
                    'original_price': p.get('original_price'),
                    'price_note': p.get('price_note', ''),
                    'badge_top': p.get('badge_top', ''),
                    'badge_top_accent': p.get('badge_top_accent', False),
                    'badge_secondary': p.get('badge_secondary', ''),
                    'telemetry': p.get('telemetry', []),
                    'stock_quantity': p.get('stock_quantity', 0),
                    'stock_label': p.get('stock_label', ''),
                    'low_stock_threshold': p.get('low_stock_threshold', 5),
                    'rating': p.get('rating', Decimal('0.00')),
                    'total_reviews': p.get('total_reviews', 0),
                    'is_active': True,
                    'is_featured': p.get('is_featured', False),
                },
            )
            self.stdout.write(self.style.SUCCESS(f"  ✓ Product: {p['name']}"))

        # ---- Promo code PRO15 ----
        PromoCode.objects.update_or_create(
            code='PRO15',
            defaults={
                'description': 'Pro Member 15% off',
                'discount_percent': Decimal('15.00'),
                'is_active': True,
            },
        )
        self.stdout.write(self.style.SUCCESS('  ✓ Promo: PRO15'))

        self.stdout.write(self.style.SUCCESS('\n✅ Shop seed complete!\n'))