from django.core.management.base import BaseCommand
from apps.reports.models import ReportTemplate


TEMPLATES = [
    {
        'key': 'revenue',
        'title': 'Revenue Report',
        'description': 'Monthly, quarterly, and annual revenue with stream breakdowns.',
        'icon': 'payments',
        'frequency': 'monthly',
        'is_featured': True,
    },
    {
        'key': 'members',
        'title': 'Member Report',
        'description': 'Growth, retention, churn, and LTV analysis.',
        'icon': 'groups',
        'frequency': 'weekly',
        'is_featured': False,
    },
    {
        'key': 'attendance',
        'title': 'Attendance Report',
        'description': 'Check-ins by day/hour, peak analysis, facility utilization.',
        'icon': 'event_available',
        'frequency': 'daily',
        'is_featured': False,
    },
    {
        'key': 'machines',
        'title': 'Machine Utilization',
        'description': 'QR scan volume, popular stations, maintenance schedule.',
        'icon': 'precision_manufacturing',
        'frequency': 'weekly',
        'is_featured': False,
    },
    {
        'key': 'trainers',
        'title': 'Trainer Performance',
        'description': 'Course sales, ratings, student progress, earnings.',
        'icon': 'school',
        'frequency': 'monthly',
        'is_featured': False,
    },
    {
        'key': 'finance',
        'title': 'Financial Statement',
        'description': 'Full P&L, expense tracking, and tax-compliant summaries.',
        'icon': 'assessment',
        'frequency': 'quarterly',
        'is_featured': True,
    },
]


class Command(BaseCommand):
    help = 'Seed sample report templates'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for t in TEMPLATES:
            obj, created = ReportTemplate.objects.update_or_create(
                key=t['key'],
                defaults={
                    'title': t['title'],
                    'description': t['description'],
                    'icon': t['icon'],
                    'frequency': t['frequency'],
                    'is_featured': t.get('is_featured', False),
                    'is_active': True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {t["title"]}'))
            else:
                updated_count += 1
                self.stdout.write(f'  ↻ Updated: {t["title"]}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Seed complete — {created_count} created, {updated_count} updated\n'
        ))