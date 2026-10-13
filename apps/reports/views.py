from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import uuid

from .models import ReportTemplate, GeneratedReport
from .serializers import ReportTemplateSerializer, GeneratedReportSerializer
from apps.admin_api.permissions import IsAdminUser


VALID_FORMATS = ('PDF', 'CSV', 'XLSX')


# ============================================
# TEMPLATES
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def templates_list(request):
    """
    GET /api/reports/templates/
    Query: ?category=...
    """
    qs = ReportTemplate.objects.filter(is_active=True)

    frequency = request.query_params.get('frequency')
    if frequency:
        qs = qs.filter(frequency=frequency)

    return Response(ReportTemplateSerializer(qs, many=True).data)


# ============================================
# GENERATE REPORT
# ============================================
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def generate_report(request):
    """
    POST /api/reports/generate/
    Body: { "template_key": "revenue", "period": "Oct 2026", "format": "PDF" }
    """
    template_key = request.data.get('template_key')
    period = (request.data.get('period') or '').strip()
    fmt = (request.data.get('format') or 'PDF').upper()

    if not template_key:
        return Response(
            {'detail': 'template_key is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if fmt not in VALID_FORMATS:
        return Response(
            {'detail': f'format must be one of {VALID_FORMATS}.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        template = ReportTemplate.objects.get(key=template_key, is_active=True)
    except ReportTemplate.DoesNotExist:
        return Response(
            {'detail': 'Template not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Generate unique report ID
    report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"

    # Fallback period: current month name
    default_period = timezone.now().strftime('%b %Y')
    final_period = period or default_period

    report = GeneratedReport.objects.create(
        template=template,
        report_id=report_id,
        name=f"{template.title} — {final_period}",
        report_type=template.key,
        period=final_period,
        format=fmt,
        size_kb=2400,  # stub — replace with actual PDF size later
        generated_by=request.user,
    )

    return Response(
        GeneratedReportSerializer(report).data,
        status=status.HTTP_201_CREATED,
    )


# ============================================
# HISTORY
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def history_list(request):
    """
    GET /api/reports/history/
    Query: ?limit=50&report_type=revenue
    """
    try:
        limit = int(request.query_params.get('limit', 50))
    except ValueError:
        limit = 50

    qs = GeneratedReport.objects.select_related('generated_by', 'template')

    report_type = request.query_params.get('report_type')
    if report_type:
        qs = qs.filter(report_type=report_type)

    return Response(GeneratedReportSerializer(qs[:limit], many=True).data)


# ============================================
# DETAIL
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def report_detail(request, report_id):
    """
    GET /api/reports/history/<report_id>/
    """
    try:
        report = GeneratedReport.objects.get(report_id=report_id)
    except GeneratedReport.DoesNotExist:
        return Response(
            {'detail': 'Report not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(GeneratedReportSerializer(report).data)


# ============================================
# DELETE
# ============================================
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def delete_report(request, report_id):
    """
    DELETE /api/reports/history/<report_id>/
    """
    try:
        report = GeneratedReport.objects.get(report_id=report_id)
    except GeneratedReport.DoesNotExist:
        return Response(
            {'detail': 'Report not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    report.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================
# DOWNLOAD (stub — returns metadata)
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def download_report(request, report_id):
    """
    GET /api/reports/history/<report_id>/download/
    Returns metadata. In production, redirect to a signed S3 URL.
    """
    try:
        report = GeneratedReport.objects.get(report_id=report_id)
    except GeneratedReport.DoesNotExist:
        return Response(
            {'detail': 'Report not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response({
        'report_id': report.report_id,
        'name': report.name,
        'format': report.format,
        'file_url': report.file_url or '',
        'size_kb': report.size_kb,
        'generated_at': report.generated_at,
    })