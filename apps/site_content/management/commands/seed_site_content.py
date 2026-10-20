from django.core.management.base import BaseCommand

from apps.site_content.models import SiteImage, SiteText
from apps.site_content.seeding import seed


class Command(BaseCommand):
    help = 'Add/refresh public-site text and image slots from apps/site_content/seed/ (never overwrites admin edits).'

    def handle(self, *args, **options):
        stats = seed(SiteText, SiteImage)
        self.stdout.write(self.style.SUCCESS(', '.join(f'{k}={v}' for k, v in stats.items())))
