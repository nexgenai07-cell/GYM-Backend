from django.contrib import admin
from .models import Facility, FacilityBooking


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'zone', 'capacity', 'current_occupancy', 'is_active']
    list_filter = ['category', 'is_active', 'zone']
    search_fields = ['name', 'code']


@admin.register(FacilityBooking)
class FacilityBookingAdmin(admin.ModelAdmin):
    list_display = ['facility', 'member', 'start_time', 'status']
    list_filter = ['status', 'facility']
    search_fields = ['member__email', 'facility__name']
    raw_id_fields = ['member', 'facility']