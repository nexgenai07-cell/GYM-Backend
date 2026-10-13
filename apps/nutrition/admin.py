from django.contrib import admin
from .models import (
    NutritionistProfile, NutritionPlan,
    MealLog, WaterIntake, DexaScan,
)


@admin.register(NutritionistProfile)
class NutritionistProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'rating', 'is_verified', 'is_accepting_clients']
    list_filter = ['is_verified', 'is_accepting_clients']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'title']
    raw_id_fields = ['user']


@admin.register(NutritionPlan)
class NutritionPlanAdmin(admin.ModelAdmin):
    list_display = ['member', 'goal', 'status', 'target_calories', 'target_protein_g', 'created_at']
    list_filter = ['status', 'goal']
    search_fields = ['member__email', 'name']
    raw_id_fields = ['member', 'nutritionist']


@admin.register(MealLog)
class MealLogAdmin(admin.ModelAdmin):
    list_display = ['member', 'meal_type', 'description', 'calories', 'protein_g', 'logged_date']
    list_filter = ['meal_type', 'logged_date']
    search_fields = ['member__email', 'description']
    raw_id_fields = ['member', 'plan']
    date_hierarchy = 'logged_date'


@admin.register(WaterIntake)
class WaterIntakeAdmin(admin.ModelAdmin):
    list_display = ['member', 'date', 'amount_ml']
    list_filter = ['date']
    search_fields = ['member__email']
    raw_id_fields = ['member']


@admin.register(DexaScan)
class DexaScanAdmin(admin.ModelAdmin):
    list_display = ['member', 'scan_date', 'body_fat_percent', 'lean_mass_kg']
    list_filter = ['scan_date']
    search_fields = ['member__email']
    raw_id_fields = ['member']
    date_hierarchy = 'scan_date'