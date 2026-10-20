from django.contrib import admin

from .models import ContactMessage, SiteImage, SiteText


@admin.register(SiteText)
class SiteTextAdmin(admin.ModelAdmin):
    list_display = ['key', 'page', 'en', 'updated_at']
    list_filter = ['page']
    search_fields = ['key', 'en', 'ar']
    readonly_fields = ['key', 'page', 'default_en', 'default_ar', 'updated_at', 'updated_by']


@admin.register(SiteImage)
class SiteImageAdmin(admin.ModelAdmin):
    list_display = ['key', 'page', 'label', 'image', 'updated_at']
    list_filter = ['page']
    search_fields = ['key', 'label']
    readonly_fields = ['key', 'page', 'default_url', 'updated_at', 'updated_by']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'name', 'email', 'topic', 'status']
    list_filter = ['status', 'topic']
    search_fields = ['name', 'email', 'message']
