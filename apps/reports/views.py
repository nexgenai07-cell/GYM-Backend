"""
Reports: CSV exports built from live data for a date range (gym time). The CSV is stored with
the report when generated, so a later download matches what was generated.

GET    /api/reports/templates/
POST   /api/reports/generate/  {template_key, start: "YYYY-MM-DD", end: "YYYY-MM-DD"}
GET    /api/reports/history/
GET    /api/reports/history/<report_id>/
GET    /api/reports/history/<report_id>/download/   → text/csv attachment
DELETE /api/reports/history/<report_id>/delete/
"""
import csv
import io
import uuid
from datetime import date, timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.admin_api.permissions import IsAdminUser

from apps.core.bilingual import header as bilingual_header

from .builders import REPORTS
from .models import GeneratedReport, ReportTemplate
from .serializers import GeneratedReportSerializer

MAX_DAYS = 366 * 2


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def templates_list(request):
    """GET /api/reports/templates/ — the reports this backend can build."""
    last = _last_by_type()
    return Response([{'key': k, 'title': t, 'description': d, 'icon': icon, 'format': 'CSV',
                      'last_generated_at': last.get(k)} for k, (t, d, icon, _) in REPORTS.items()])


def _last_by_type():
    out = {}
    for r in GeneratedReport.objects.order_by('-generated_at').values('report_type', 'generated_at'):
        out.setdefault(r['report_type'], r['generated_at'])
    return out


def _parse(v):
    try:
        return date.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def generate_report(request):
    key = request.data.get('template_key')
    if key not in REPORTS:
        return Response({'detail': 'Choose a report.'}, status=status.HTTP_400_BAD_REQUEST)
    today = timezone.localdate()
    start = _parse(request.data.get('start')) or today.replace(day=1)
    end = _parse(request.data.get('end')) or today
    if start > end:
        return Response({'end': ['The end date is before the start date.']}, status=status.HTTP_400_BAD_REQUEST)
    if end > today:
        end = today
    if (end - start).days > MAX_DAYS:
        return Response({'start': ['Pick a range of two years or less.']}, status=status.HTTP_400_BAD_REQUEST)

    title, description, icon, build = REPORTS[key]
    header, rows = build(start, end)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(bilingual_header(header))
    w.writerows(rows)
    content = buf.getvalue()

    template, _ = ReportTemplate.objects.get_or_create(
        key=key, defaults={'title': title, 'description': description, 'icon': icon})
    label = (start.strftime('%b %Y') if start.day == 1 and (end + timedelta(days=1)).day == 1 and start.month == end.month
             else f'{start:%d %b %Y} – {end:%d %b %Y}')
    report = GeneratedReport.objects.create(
        template=template, report_id=f'RPT-{uuid.uuid4().hex[:6].upper()}', name=f'{title} — {label}',
        report_type=key, period=label[:60], format='CSV', content=content,
        size_kb=max(1, round(len(content.encode('utf-8')) / 1024)), period_start=start, period_end=end,
        row_count=len(rows), generated_by=request.user)
    return Response(GeneratedReportSerializer(report).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def history_list(request):
    try:
        limit = max(1, min(int(request.query_params.get('limit', 50)), 200))
    except ValueError:
        limit = 50
    qs = GeneratedReport.objects.select_related('generated_by').defer('content')
    if request.query_params.get('report_type'):
        qs = qs.filter(report_type=request.query_params['report_type'])
    return Response(GeneratedReportSerializer(qs[:limit], many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def report_detail(request, report_id):
    report = get_object_or_404(GeneratedReport.objects.defer('content'), report_id=report_id)
    return Response(GeneratedReportSerializer(report).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def delete_report(request, report_id):
    get_object_or_404(GeneratedReport, report_id=report_id).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def download_report(request, report_id):
    report = get_object_or_404(GeneratedReport, report_id=report_id)
    if not report.content:
        return Response({'detail': 'This report was created before downloads existed — generate it again.'},
                        status=status.HTTP_404_NOT_FOUND)
    resp = HttpResponse('﻿' + report.content, content_type='text/csv; charset=utf-8')   # BOM → Excel reads UTF-8
    resp['Content-Disposition'] = f'attachment; filename="{report.report_id}-{report.report_type}.csv"'
    return resp
