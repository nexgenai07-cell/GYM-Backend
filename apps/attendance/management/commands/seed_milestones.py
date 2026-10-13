from django.core.management.base import BaseCommand
from apps.attendance.models import Milestone


MILESTONES = [
    {
        'tier': 'Tier 01 • Starter',
        'title': '15-Day Consistency',
        'description': 'Granted voucher: 15% OFF Performance Fuel & Apparel at the Gym Pro Shop.',
        'icon': 'task_alt',
        'tier_type': 'consistency',
        'target_days': 15,
        'reward_value': '15% OFF voucher',
        'reward_code': 'CONSISTENT-15',
        'display_order': 1,
    },
    {
        'tier': 'Tier 02 • Beast Mode',
        'title': '30-Day Beast Mode',
        'description': 'Complimentary session in High-Subzero Cryo Pods ($65 value).',
        'icon': 'progress_activity',
        'tier_type': 'streak',
        'target_days': 30,
        'reward_value': '$65 Cryo Session',
        'reward_code': 'CRYO-30',
        'display_order': 2,
    },
    {
        'tier': 'Tier 03 • Century Club',
        'title': 'Century Club 100 Days',
        'description': 'Engraved Black Titanium Barbell Collar + 1-Year VIP Locker Privilege.',
        'icon': 'lock',
        'tier_type': 'challenge',
        'target_days': 100,
        'reward_value': 'Titanium Collar + VIP Locker',
        'reward_code': 'CENTURY-100',
        'display_order': 3,
    },
]


class Command(BaseCommand):
    help = 'Seed milestone tiers'

    def handle(self, *args, **options):
        Milestone.objects.all().delete()
        for m in MILESTONES:
            Milestone.objects.create(**m)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(MILESTONES)} milestones'))