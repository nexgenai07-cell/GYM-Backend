# apps/nutrition/management/commands/seed_nutritionists.py
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from apps.nutrition.models import (
    NutritionistProfile, NutritionPlan,
    MealLog, WaterIntake, DexaScan,
)

User = get_user_model()


NUTRITIONISTS = [
    {
        'email': 'dr.chen@smartgym.io',
        'first': 'Elena', 'last': 'Chen',
        'title': 'Head of Metabolic Architecture',
        'credentials': 'RD, CSSD, PhD',
        'bio': 'Olympic-level sports dietitian specializing in body recomposition, periodized nutrition, and clinical metabolic optimization.',
        'rating': Decimal('4.90'), 'reviews': 142, 'clients': 320,
        'years': 12, 'rate': Decimal('220.00'),
        'specialties': ['Hypertrophy', 'Recomp', 'Endurance'],
        'photo_url': 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=800',
    },
    {
        'email': 'marcus@smartgym.io',
        'first': 'Marcus', 'last': 'Thorne',
        'title': 'Performance Nutritionist',
        'credentials': 'MS, RD',
        'bio': 'Former NFL nutrition consultant. Precision macro periodization and in-season fueling strategies for elite athletes.',
        'rating': Decimal('4.70'), 'reviews': 98, 'clients': 210,
        'years': 8, 'rate': Decimal('180.00'),
        'specialties': ['Fat Loss', 'Performance'],
        'photo_url': 'https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=800',
    },
    {
        'email': 'priya@smartgym.io',
        'first': 'Priya', 'last': 'Raman',
        'title': 'Clinical Sports Dietitian',
        'credentials': 'RD, LD',
        'bio': 'Focus on metabolic health, gut microbiome optimization, and sustainable body composition transformation.',
        'rating': Decimal('4.60'), 'reviews': 76, 'clients': 150,
        'years': 6, 'rate': Decimal('150.00'),
        'specialties': ['Gut Health', 'Recomp'],
        'photo_url': 'https://images.unsplash.com/photo-1594824476967-48c8b964273f?w=800',
    },
]


class Command(BaseCommand):
    help = 'Seed nutritionists + demo DEXA scan + sample meals'

    def handle(self, *args, **options):
        # ---------- Nutritionists ----------
        for data in NUTRITIONISTS:
            user, created = User.objects.get_or_create(
                email=data['email'],
                defaults={
                    'first_name': data['first'],
                    'last_name': data['last'],
                    'role': 'nutritionist',
                },
            )
            if created:
                user.set_password('password123')
                user.save()

            NutritionistProfile.objects.update_or_create(
                user=user,
                defaults={
                    'title': data['title'],
                    'credentials': data['credentials'],
                    'bio': data['bio'],
                    'rating': data['rating'],
                    'total_reviews': data['reviews'],
                    'total_clients': data['clients'],
                    'years_experience': data['years'],
                    'hourly_rate': data['rate'],
                    'specialties': data['specialties'],
                    'photo_url': data['photo_url'],
                    'is_verified': True,
                    'is_accepting_clients': True,
                },
            )
            self.stdout.write(self.style.SUCCESS(f"  ✓ {data['first']} {data['last']}"))

        # ---------- Demo member data (DEXA + meals + water) ----------
        member = User.objects.filter(role='member').first()
        if not member:
            member = User.objects.first()

        if member:
            # DEXA — 3 scans over 6 months so sparkline has history
            base = date.today()
            dexa_data = [
                (base - timedelta(days=180), 88.0, 22.5, 68.2, 19.8, 1.2),
                (base - timedelta(days=90),  85.2, 20.1, 68.1, 17.1, 1.0),
                (base - timedelta(days=30),  82.5, 18.4, 67.3, 15.2, 0.8),
            ]
            for scan_date, w, bf, lm, fm, vf in dexa_data:
                DexaScan.objects.update_or_create(
                    member=member, scan_date=scan_date,
                    defaults={
                        'weight_kg': w, 'body_fat_percent': bf,
                        'lean_mass_kg': lm, 'fat_mass_kg': fm,
                        'visceral_fat_kg': vf,
                    },
                )

            # Today's meals
            MealLog.objects.filter(
                member=member, logged_date=base
            ).delete()

            MealLog.objects.create(
                member=member, meal_type='breakfast',
                description='Oats, whey, blueberries',
                calories=520, protein_g=38, carbs_g=68, fats_g=12,
            )
            MealLog.objects.create(
                member=member, meal_type='lunch',
                description='Grilled chicken, brown rice, broccoli',
                calories=680, protein_g=52, carbs_g=72, fats_g=16,
            )

            # Water today
            WaterIntake.objects.update_or_create(
                member=member, date=base,
                defaults={'amount_ml': 1500},
            )

            self.stdout.write(self.style.SUCCESS(
                f"\n  ✓ Seeded demo data for: {member.email}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                '  ⚠ No member user found — skipping DEXA/meal seed'
            ))

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Nutrition seed complete!\n'
        ))