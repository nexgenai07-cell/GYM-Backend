from django.core.management.base import BaseCommand
from apps.facilities.models import Facility


FACILITIES = [
    {'code': 'FAC-01', 'name': 'Heavy Iron Arena', 'category': 'gym', 'zone': 'Sector 01', 'capacity': 18, 'current_occupancy': 17, 'temp_celsius': 22, 'amenities': ['18 Comp Racks', 'Calibrated Plates', 'VBT Sensors']},
    {'code': 'FAC-02', 'name': 'Combat & Striking Pit', 'category': 'combat', 'zone': 'Sector 02', 'capacity': 16, 'current_occupancy': 12, 'temp_celsius': 21, 'amenities': ['16 Heavy Bags', 'Sparring Ring', 'Impact Sensors']},
    {'code': 'FAC-03', 'name': 'Olympic Hydro Matrix', 'category': 'aquatic', 'zone': 'Sector 03', 'capacity': 8, 'current_occupancy': 6, 'temp_celsius': 26.2, 'amenities': ['8 Lanes', 'Chlorine Monitoring', 'Underwater Timing']},
    {'code': 'FAC-04', 'name': 'Steam & Cryo Matrix', 'category': 'recovery', 'zone': 'Sector 04', 'capacity': 4, 'current_occupancy': 4, 'temp_celsius': -110, 'amenities': ['4 Cryo Pods', 'Steam Room', 'Nitrogen Monitoring']},
    {'code': 'FAC-05', 'name': 'FIBA Hardcourt', 'category': 'sports', 'zone': 'Sector 05', 'capacity': 20, 'current_occupancy': 8, 'temp_celsius': 20, 'amenities': ['Court Lighting', 'Shot Clocks', 'Scoreboard']},
    {'code': 'FAC-06', 'name': 'Sprint Track & Turf', 'category': 'sports', 'zone': 'Sector 06', 'capacity': 12, 'current_occupancy': 8, 'temp_celsius': 21, 'amenities': ['50m Sprint Lanes', 'Sled Turf', 'Laser Gates']},
    {'code': 'FAC-07', 'name': 'Mobility & Yoga Deck', 'category': 'recovery', 'zone': 'Sector 07', 'capacity': 24, 'current_occupancy': 14, 'temp_celsius': 24, 'amenities': ['Yoga Mats', 'Balance Tools', 'Ambient Sound']},
    {'code': 'FAC-08', 'name': 'Cardio Deck Alpha', 'category': 'gym', 'zone': 'Sector 08', 'capacity': 20, 'current_occupancy': 12, 'temp_celsius': 21, 'amenities': ['Treadmills', 'Bikes', 'Rowers']},
]


class Command(BaseCommand):
    help = 'Seed sample facilities'

    def handle(self, *args, **options):
        Facility.objects.all().delete()
        for f in FACILITIES:
            Facility.objects.create(**f)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(FACILITIES)} facilities'))