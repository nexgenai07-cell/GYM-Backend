from django.contrib import admin
from .models import (
    Exercise, Workout, WorkoutExercise, WorkoutSet,
    PersonalRecord, WorkoutTemplate, TemplateExercise,
)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'primary_muscle', 'qr_tag_id', 'is_active']
    list_filter = ['category', 'primary_muscle', 'is_compound', 'is_active']
    search_fields = ['name', 'qr_tag_id', 'machine_id']


class WorkoutSetInline(admin.TabularInline):
    model = WorkoutSet
    extra = 0


class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 0


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ['member', 'name', 'status', 'started_at', 'total_tonnage_kg']
    list_filter = ['status', 'started_at']
    search_fields = ['member__email', 'name']
    raw_id_fields = ['member']
    inlines = [WorkoutExerciseInline]


@admin.register(PersonalRecord)
class PersonalRecordAdmin(admin.ModelAdmin):
    list_display = ['member', 'exercise', 'best_weight_kg', 'best_reps', 'achieved_at']
    list_filter = ['exercise__category']
    search_fields = ['member__email', 'exercise__name']
    raw_id_fields = ['member', 'exercise']


class TemplateExerciseInline(admin.TabularInline):
    model = TemplateExercise
    extra = 0


@admin.register(WorkoutTemplate)
class WorkoutTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'difficulty', 'estimated_duration_minutes', 'is_active']
    list_filter = ['category', 'difficulty', 'is_active']
    search_fields = ['name']
    inlines = [TemplateExerciseInline]