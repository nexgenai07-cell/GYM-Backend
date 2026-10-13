from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.cms.models import Article


ARTICLES = [
    {
        'article_id': 'ART-001',
        'title': 'The Velocity-Based Training Protocol',
        'category': 'Training',
        'status': 'published',
        'excerpt': 'How VBT is rewriting strength standards.',
        'content': 'Velocity-based training measures bar speed to calibrate load...',
        'author_name': 'Dr. Elias Vance',
        'read_time_minutes': 8,
        'views_count': 8420,
        'is_featured': True,
        'cover_image_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuBbVGUTzt-u3vCjuQm_-WPuCAir7kfIo0jNgxezUtVIimLofLZRy9QI5mZTSGx8Dy_c66iqhRXlVin-9XEbtpvISu1YW54EmfrvrXOno6bCtDm9eSuLOq7qTsklSf6kKZkKYRgqOmSGCCDBTG1xp9cIj59iSzPkoTgV3uMQrRF563W0On8Qjj8RF_qvcAcC_NshTj2yioD8GnydTr8YknFNWPfYn1C9arJIgraKl37Wkh6IR64K40MQog',
    },
    {
        'article_id': 'ART-002',
        'title': 'Decoding VO2 Max for Strength Athletes',
        'category': 'Biometrics',
        'status': 'published',
        'excerpt': 'Why conditioning matters for lifters.',
        'author_name': 'Sarah Lin',
        'read_time_minutes': 6,
        'views_count': 5240,
        'cover_image_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuC3Tcijljr1m1Sr5JlL-JNRZE5OBywWXX3FmpxvulClFJwbk4NHl7I2DhYKgPzYeMPafhlkE60Ef_5oDIxlc5OjVEIpbtVeQhR88v3r3Ve9IOd0T9fWZJKWTfJ4ncptzyueYfnMcpn-9YFKTlryU7sNuXeEdnUT0YiD5YSPQ1VxgvEBifC3xzEsYepB9hqpSZEFyBSqDsNaoTr5tUFOODDf0Z3XaAYytH707J692DgNzL94WdnOLkcGUw',
    },
    {
        'article_id': 'ART-003',
        'title': 'Glycogen Timing Protocols',
        'category': 'Nutrition',
        'status': 'published',
        'excerpt': 'Fuel your training with precision.',
        'author_name': 'Dr. Sarah Lin',
        'read_time_minutes': 7,
        'views_count': 3840,
        'cover_image_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuDwCwwQEM7MZyNuOOi7yIAIuX7OAVomaaeONSwQtbib7WwkGROwW_78oKkT3r9TEqcoTUyFEKRuGIcQw-2lRQNVLCrhJAO2Keg0YpGdedHeuTx7XhOy4okgceriZ9nf9X9es47Nf4HwZeAD4erdrdz3owMLOUBePPHQacAPzq_Aw-4DupJ4Ttkf7qklS-a61vvnVudoAazAaDgqNvTE6nRQWI4spVFWOnl-dC5LHjsIKi7OBfgBulsumg',
    },
    {
        'article_id': 'ART-005',
        'title': 'Understanding Force-Velocity Profiling',
        'category': 'Training',
        'status': 'draft',
        'excerpt': 'Coming soon',
        'author_name': 'Dr. Elias Vance',
        'read_time_minutes': 9,
        'views_count': 0,
        'cover_image_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuBX7EKYzKmkKpEF0irfKKhV-V2X2SSyUwdz6E8S_ezW6zx4oqVHfMIgxsKNPfpPfczRX3Kn6FHPpRgLF-tpGHWNFff3NARbnhcNDVwjYYts1brD1rTQ3YFu2IIhG3WVgQMC6qGZE1mSQXJALNUWUJR2rZPwIjyHjC0CiPbKqaHNg8V4HkFsL9jvyXuMjcNLEF97PogR7rKfzr-pc7Cy9d5fzkyV-Uq83oAcr0mZqGk0IgoZH6OMA0Ba7Q',
    },
]


class Command(BaseCommand):
    help = 'Seed sample articles'

    def handle(self, *args, **options):
        Article.objects.all().delete()
        for a in ARTICLES:
            if a.get('status') == 'published':
                a['published_at'] = timezone.now()
            Article.objects.create(**a)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(ARTICLES)} articles'))