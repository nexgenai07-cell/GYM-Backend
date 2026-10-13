from django.contrib import admin
from .models import GymClass, ClassEnrollment


@admin.register(GymClass)
class GymClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'level', 'day_of_week', 'start_time', 'capacity', 'is_active']
    list_filter = ['category', 'level', 'is_active', 'day_of_week']
    search_fields = ['name']


@admin.register(ClassEnrollment)
class ClassEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['gym_class', 'member', 'status', 'enrolled_at']
    list_filter = ['status']
    raw_id_fields = ['member', 'gym_class']