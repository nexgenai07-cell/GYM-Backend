from django.contrib import admin
from .models import ReportTemplate, GeneratedReport


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ['title', 'key', 'frequency', 'is_active', 'is_featured']
    list_filter = ['frequency', 'is_active', 'is_featured']


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ['report_id', 'name', 'report_type', 'period', 'format', 'generated_at']
    list_filter = ['report_type', 'format']
    search_fields = ['report_id', 'name']
    raw_id_fields = ['generated_by', 'template']
    date_hierarchy = 'generated_at'