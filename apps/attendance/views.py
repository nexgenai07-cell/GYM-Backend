from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Avg, Sum, Count
from datetime import timedelta, date
from calendar import monthrange
import csv
from io import StringIO
from django.http import HttpResponse

from .models import Milestone, MemberMilestone
from .serializers import MilestoneSerializer
from apps.members.models import CheckIn


# ============================================
# SUMMARY
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def summary(request):
    """
    GET /api/attendance/summary/
    """
    user = request.user
    today = timezone.localdate()
    month_start = today.replace(day=1)

    all_ci = CheckIn.objects.filter(member=user)
    month_ci = all_ci.filter(check_in_time__date__gte=month_start)

    # Current streak
    streak = 0
    check_date = today
    while all_ci.filter(check_in_time__date=check_date).exists():
        streak += 1
        check_date -= timedelta(days=1)

    # Time totals
    total_minutes = all_ci.aggregate(t=Sum('duration_minutes'))['t'] or 0
    month_minutes = month_ci.aggregate(t=Sum('duration_minutes'))['t'] or 0

    # First check-in time (optimal window)
    first_today = all_ci.filter(check_in_time__date=today).order_by('check_in_time').first()
    prime_window = first_today.check_in_time.strftime('%H:%M') if first_today else '—'

    return Response({
        'current_streak': {
            'value': streak,
            'unit': 'Days',
            'footer': f'Personal Best: {streak} Days',
            'progress': min(100, int((streak / 24) * 100)) if streak else 0,
        },
        'month_check_ins': {
            'value': month_ci.count(),
            'unit': 'Visits',
            'badge': 'Top 4% Campus Elite' if month_ci.count() >= 20 else None,
            'footer': 'Cycle Goal: 26 Sessions',
            'footer_right': f'{min(100, int((month_ci.count() / 26) * 100))}%',
        },
        'workout_hours': {
            'value': round(total_minutes / 60, 1),
            'unit': 'Hrs',
            'badge': None,
            'footer': f'Month total: {round(month_minutes / 60, 1)}h',
            'footer_right': f'Avg {int(total_minutes / max(1, all_ci.count()))}m',
        },
        'prime_window': {
            'value': prime_window,
            'unit': '',
            'badge': 'Evening Prime · 78% Session Affinity',
            'footer': 'Recovery index: 94%',
            'footer_right': 'Bio-Synced',
        },
        'total_check_ins': all_ci.count(),
    })


# ============================================
# CHECK-INS CRUD
# ============================================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def check_ins(request):
    """
    GET  /api/attendance/check-ins/    → list
    POST /api/attendance/check-ins/    → create
    """
    if request.method == 'GET':
        qs = CheckIn.objects.filter(member=request.user)[:100]
        return Response([{
            'id': c.id,
            'facility': c.facility,
            'zone': c.zone,
            'check_in_time': c.check_in_time,
            'check_out_time': c.check_out_time,
            'duration_minutes': c.duration_minutes,
        } for c in qs])

    # POST — create check-in
    facility = request.data.get('facility', 'Metro Station Core 01')
    zone = request.data.get('zone', '')

    # Prevent double check-in within same day
    today = timezone.localdate()
    existing = CheckIn.objects.filter(
        member=request.user,
        check_in_time__date=today,
        check_out_time__isnull=True,
    ).first()

    if existing:
        return Response({
            'detail': 'Already checked in — check out first.',
            'check_in_id': existing.id,
        }, status=400)

    ci = CheckIn.objects.create(
        member=request.user,
        facility=facility,
        zone=zone,
    )

    # Update milestone progress for streak
    _update_streak_milestones(request.user)

    return Response({
        'id': ci.id,
        'facility': ci.facility,
        'zone': ci.zone,
        'check_in_time': ci.check_in_time,
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_out(request, check_in_id):
    """
    POST /api/attendance/check-ins/<id>/check-out/
    """
    try:
        ci = CheckIn.objects.get(id=check_in_id, member=request.user)
    except CheckIn.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    if ci.check_out_time:
        return Response({'detail': 'Already checked out.'}, status=400)

    ci.check_out_time = timezone.now()
    duration = (ci.check_out_time - ci.check_in_time).total_seconds() / 60
    ci.duration_minutes = int(duration)
    ci.save()

    return Response({
        'id': ci.id,
        'duration_minutes': ci.duration_minutes,
    })


# ============================================
# LEDGER (paginated + filterable)
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ledger(request):
    """
    GET /api/attendance/ledger/?page=1&per_page=5&zone=&from=&to=
    """
    page = int(request.query_params.get('page', 1))
    per_page = int(request.query_params.get('per_page', 5))

    qs = CheckIn.objects.filter(member=request.user).order_by('-check_in_time')

    # Filters
    zone = request.query_params.get('zone')
    if zone:
        qs = qs.filter(zone__icontains=zone)

    from_date = request.query_params.get('from')
    if from_date:
        qs = qs.filter(check_in_time__date__gte=from_date)

    to_date = request.query_params.get('to')
    if to_date:
        qs = qs.filter(check_in_time__date__lte=to_date)

    total = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    page_items = qs[start:end]

    results = []
    for c in page_items:
        in_time = c.check_in_time
        out_time = c.check_out_time
        duration = c.duration_minutes

        is_active = out_time is None
        status = 'Streak' if duration else 'Active'

        results.append({
            'id': c.id,
            'date': in_time.strftime('%b %d, %Y'),
            'status': f'Streak #{c.id % 30}',  # demo pattern
            'statusType': 'active' if is_active else 'default',
            'entry': in_time.strftime('%H:%M:%S'),
            'exit': 'ACTIVE SESSION' if is_active else out_time.strftime('%H:%M:%S'),
            'exitActive': is_active,
            'duration': f'{duration}m' if duration else 'Active',
            'durationActive': is_active,
            'zones': [c.zone] if c.zone else [c.facility],
            'reps': '—',      # filled by workout log later
            'volume': '—',    # filled by workout log later
        })

    return Response({
        'results': results,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ledger_export(request):
    """
    GET /api/attendance/ledger/export/ → CSV download
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_ledger.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Entry', 'Exit', 'Duration (min)', 'Facility', 'Zone'])

    for c in CheckIn.objects.filter(member=request.user).order_by('-check_in_time'):
        writer.writerow([
            c.check_in_time.strftime('%Y-%m-%d'),
            c.check_in_time.strftime('%H:%M'),
            c.check_out_time.strftime('%H:%M') if c.check_out_time else 'ACTIVE',
            c.duration_minutes or 0,
            c.facility,
            c.zone,
        ])

    return response


# ============================================
# HEATMAP
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def heatmap(request):
    """
    GET /api/attendance/heatmap/?year=2025
    Returns 52 weeks × 7 days matrix with intensity level 0-4.
    """
    year = int(request.query_params.get('year', timezone.localdate().year))
    today = timezone.localdate()

    # Build 52-week grid aligned to Monday start
    start_date = date(year, 1, 1)
    # Align to Monday
    while start_date.weekday() != 0:
        start_date -= timedelta(days=1)

    # Count check-ins per day
    daily_counts = {}
    ci_qs = CheckIn.objects.filter(
        member=request.user,
        check_in_time__year=year,
    ).values('check_in_time__date').annotate(count=Count('id'))

    for row in ci_qs:
        daily_counts[row['check_in_time__date']] = row['count']

    weeks = []
    cursor = start_date
    for w in range(52):
        week = []
        for d in range(7):
            day = cursor + timedelta(days=d)
            count = daily_counts.get(day, 0)
            # Intensity 0-4
            if count == 0:
                level = 0
            elif count == 1:
                level = 2
            elif count == 2:
                level = 3
            else:
                level = 4
            week.append({
                'date': day.isoformat(),
                'count': count,
                'level': level,
                'is_future': day > today,
            })
        weeks.append(week)
        cursor += timedelta(days=7)

    return Response({
        'year': year,
        'weeks': weeks,
    })


# ============================================
# MILESTONES
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def milestones(request):
    """
    GET /api/attendance/milestones/
    """
    qs = Milestone.objects.filter(is_active=True)
    return Response(MilestoneSerializer(qs, many=True, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def claim_milestone(request, milestone_id):
    """
    POST /api/attendance/milestones/<id>/claim/
    """
    try:
        milestone = Milestone.objects.get(id=milestone_id)
    except Milestone.DoesNotExist:
        return Response({'detail': 'Milestone not found.'}, status=404)

    mm, _ = MemberMilestone.objects.get_or_create(
        member=request.user,
        milestone=milestone,
    )

    if mm.status != 'active':
        return Response(
            {'detail': 'Milestone is not ready to claim.'},
            status=400,
        )

    mm.status = 'claimed'
    mm.claimed_at = timezone.now()
    mm.save()

    return Response({
        'id': mm.id,
        'milestone': milestone.title,
        'status': 'claimed',
        'reward_code': milestone.reward_code,
    })


# ============================================
# HOURLY CURVE
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hourly(request):
    """
    GET /api/attendance/hourly/
    Returns a 24h histogram of the member's check-in times
    + the campus occupancy curve (all members).
    """
    hours = list(range(24))
    member_buckets = {h: 0 for h in hours}
    campus_buckets = {h: 0 for h in hours}

    # Member's check-ins
    for c in CheckIn.objects.filter(member=request.user):
        h = c.check_in_time.hour
        member_buckets[h] += 1

    # Campus check-ins (all members)
    for c in CheckIn.objects.all():
        h = c.check_in_time.hour
        campus_buckets[h] += 1

    return Response({
        'member': [{'hour': h, 'count': member_buckets[h]} for h in hours],
        'campus': [{'hour': h, 'count': campus_buckets[h]} for h in hours],
        'peak_hour': max(member_buckets, key=member_buckets.get) if any(member_buckets.values()) else 18,
    })


# ============================================
# ARENAS (zones/facilities snapshot)
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def arenas(request):
    """
    GET /api/attendance/arenas/
    Top 3 arenas the member visits most.
    """
    from apps.facilities.models import Facility

    # Aggregate check-ins per zone
    zone_counts = (
        CheckIn.objects
        .filter(member=request.user)
        .exclude(zone='')
        .values('zone')
        .annotate(count=Count('id'))
        .order_by('-count')[:3]
    )

    snapshots = []
    for z in zone_counts:
        facility = Facility.objects.filter(name__icontains=z['zone'].split(' ')[0]).first()
        snapshots.append({
            'tag': 'Zone Leaderboard' if len(snapshots) == 0 else 'Zone Focus',
            'tagAccent': len(snapshots) == 0,
            'title': z['zone'],
            'description': f'{z["count"]} check-ins recorded at this zone.',
            'image': '',  # will be filled by frontend if needed
            'count': z['count'],
        })

    return Response(snapshots)


# ============================================
# AUTO MILESTONE UPDATER
# ============================================
def _update_streak_milestones(user):
    """Called after each check-in. Updates streak-based milestone progress."""
    today = timezone.localdate()
    check_ins = CheckIn.objects.filter(member=user)

    # Current streak
    streak = 0
    check_date = today
    while check_ins.filter(check_in_time__date=check_date).exists():
        streak += 1
        check_date -= timedelta(days=1)

    # Update each milestone
    for milestone in Milestone.objects.filter(is_active=True):
        mm, _ = MemberMilestone.objects.get_or_create(
            member=user, milestone=milestone,
        )
        mm.current_days = streak
        mm.progress = min(100, int((streak / milestone.target_days) * 100))

        if mm.status == 'claimed':
            continue

        if streak >= milestone.target_days:
            mm.status = 'active'   # ready to claim
        else:
            mm.status = 'locked' if streak == 0 else 'active'

        mm.save()