from django.contrib import admin
from .models import (
    TrainerProfile, TrainerAvailability,
    Course, CourseModule, Enrollment,
    TrainerSession, CourseReview, TrainerReview,
)


class TrainerAvailabilityInline(admin.TabularInline):
    model = TrainerAvailability
    extra = 0


@admin.register(TrainerProfile)
class TrainerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'rating', 'total_students', 'is_verified', 'is_accepting_clients']
    list_filter = ['is_verified', 'is_accepting_clients']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'title']
    raw_id_fields = ['user']
    inlines = [TrainerAvailabilityInline]


class CourseModuleInline(admin.TabularInline):
    model = CourseModule
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'trainer', 'category', 'level', 'status', 'price', 'is_featured']
    list_filter = ['status', 'category', 'level', 'is_featured']
    search_fields = ['title', 'trainer__user__email']
    raw_id_fields = ['trainer']
    inlines = [CourseModuleInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['member', 'course', 'status', 'progress_percent', 'enrolled_at']
    list_filter = ['status']
    search_fields = ['member__email', 'course__title']
    raw_id_fields = ['member', 'course']


@admin.register(TrainerSession)
class TrainerSessionAdmin(admin.ModelAdmin):
    list_display = ['member', 'trainer', 'scheduled_at', 'status', 'duration_minutes']
    list_filter = ['status']
    search_fields = ['member__email', 'trainer__user__email']
    raw_id_fields = ['member', 'trainer']


@admin.register(CourseReview)
class CourseReviewAdmin(admin.ModelAdmin):
    list_display = ['course', 'member', 'rating', 'created_at']
    list_filter = ['rating']
    raw_id_fields = ['course', 'member']


@admin.register(TrainerReview)
class TrainerReviewAdmin(admin.ModelAdmin):
    list_display = ['trainer', 'member', 'rating', 'created_at']
    list_filter = ['rating']
    raw_id_fields = ['trainer', 'member']