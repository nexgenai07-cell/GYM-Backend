from django.db import models
from django.conf import settings
from apps.catalog.models import TrainerProfile


class GymClass(models.Model):
    """A scheduled fitness class."""
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('all_levels', 'All Levels'),
    ]
    CATEGORY_CHOICES = [
        ('strength', 'Strength'),
        ('hiit', 'HIIT'),
        ('combat', 'Combat'),
        ('mobility', 'Mobility'),
        ('endurance', 'Endurance'),
        ('olympic', 'Olympic Lifting'),
        ('recovery', 'Recovery'),
    ]

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='all_levels')
    description = models.TextField(blank=True)

    trainer = models.ForeignKey(
        TrainerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classes',
    )

    day_of_week = models.IntegerField()  # 0 = Mon, 6 = Sun
    start_time = models.TimeField()
    duration_minutes = models.IntegerField(default=60)

    capacity = models.IntegerField(default=10)
    location = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gym_classes'
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.name} @ {self.day_of_week} {self.start_time}"


class ClassEnrollment(models.Model):
    """A member enrollment in a gym class."""
    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('waitlist', 'Waitlist'),
        ('attended', 'Attended'),
        ('no_show', 'No Show'),
        ('cancelled', 'Cancelled'),
    ]

    gym_class = models.ForeignKey(GymClass, on_delete=models.CASCADE, related_name='enrollments')
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_enrollments',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='enrolled')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'class_enrollments'
        unique_together = ['gym_class', 'member']

    def __str__(self):
        return f"{self.gym_class.name} — {self.member.email}"