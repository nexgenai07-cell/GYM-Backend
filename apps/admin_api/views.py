# apps/admin_api/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .permissions import IsAdminUser
from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan, CheckIn
from apps.workouts.models import Workout, WorkoutSet, PersonalRecord, Exercise
from apps.catalog.models import TrainerProfile, Course, Enrollment, TrainerSession
from apps.payments.models import Transaction, Invoice, LockerCredit
from apps.shop.models import Product, Order
from apps.nutrition.models import NutritionistProfile, NutritionPlan


# ============================================
# OVERVIEW / DASHBOARD
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def overview(request):
    """
    GET /api/admin/overview/
    """
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    total_members = User.objects.filter(role='member').count()
    active_members = Membership.objects.filter(status='active').count()
    expiring_soon = Membership.objects.filter(
        status='active',
        expiry_date__lte=(timezone.localdate() + timedelta(days=14))
    ).count()

    recent_txns = Transaction.objects.filter(
        status='settled',
        created_at__gte=thirty_days_ago,
    )
    revenue_30d = recent_txns.aggregate(t=Sum('amount'))['t'] or 0

    workouts_30d = Workout.objects.filter(
        status='completed',
        completed_at__gte=thirty_days_ago,
    ).count()

    today = timezone.localdate()
    check_ins_today = CheckIn.objects.filter(check_in_time__date=today).count()

    active_courses = Course.objects.filter(status='published').count()
    pending_courses = Course.objects.filter(status='pending').count()

    orders_30d = Order.objects.filter(created_at__gte=thirty_days_ago).count()

    return Response({
        'members': {
            'total': total_members,
            'active_memberships': active_members,
            'expiring_soon': expiring_soon,
        },
        'revenue': {
            'last_30d': float(revenue_30d),
            'transaction_count': recent_txns.count(),
        },
        'activity': {
            'workouts_30d': workouts_30d,
            'check_ins_today': check_ins_today,
            'orders_30d': orders_30d,
        },
        'content': {
            'active_courses': active_courses,
            'pending_approvals': pending_courses,
        },
    })


# ============================================
# MEMBERS ADMIN
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def members_list(request):
    """
    GET /api/admin/members/
    Query: ?search=&status=&role=
    """
    qs = User.objects.all().order_by('-created_at')

    role = request.query_params.get('role')
    if role and role != 'all':
        qs = qs.filter(role=role)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(username__icontains=search)
        )

    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(qs, request)

    def full_name(u):
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        return f"{u.first_name} {u.last_name}".strip() or u.email

    data = [{
        'id': u.id,
        'email': u.email,
        'username': u.username,
        'full_name': full_name(u),
        'role': u.role,
        'phone': getattr(u, 'phone', '') or '',
        'is_verified': u.is_verified,
        'is_active': u.is_active,
        'created_at': u.created_at,
    } for u in page]

    return paginator.get_paginated_response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def member_detail(request, user_id):
    """
    GET /api/admin/members/<id>/
    """
    try:
        u = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    membership = getattr(u, 'membership', None)
    workouts = Workout.objects.filter(member=u).count()
    prs = PersonalRecord.objects.filter(member=u).count()
    transactions = Transaction.objects.filter(member=u).count()

    def full_name(u):
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        return f"{u.first_name} {u.last_name}".strip() or u.email

    return Response({
        'id': u.id,
        'email': u.email,
        'username': u.username,
        'full_name': full_name(u),
        'role': u.role,
        'phone': getattr(u, 'phone', '') or '',
        'is_verified': u.is_verified,
        'is_active': u.is_active,
        'created_at': u.created_at,
        'membership': {
            'plan': membership.plan.display_name if membership else None,
            'status': membership.status if membership else None,
            'expiry_date': membership.expiry_date if membership else None,
            'lifetime_value': float(membership.lifetime_value) if membership else 0,
        } if membership else None,
        'stats': {
            'total_workouts': workouts,
            'personal_records': prs,
            'total_transactions': transactions,
        },
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def update_member(request, user_id):
    """
    PATCH /api/admin/members/<id>/update/
    """
    try:
        u = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    allowed = ['first_name', 'last_name', 'phone', 'role', 'is_verified', 'is_active']
    for field in allowed:
        if field in request.data:
            setattr(u, field, request.data[field])
    u.save()

    return Response({'detail': 'Member updated.', 'id': u.id})


# ============================================
# MEMBER STATS + ACTIONS
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def member_stats(request):
    """
    GET /api/admin/members/stats/
    """
    today = timezone.localdate()
    week_ahead = today + timedelta(days=7)

    total = User.objects.filter(role='member').count()
    active = User.objects.filter(role='member', is_active=True).count()
    verified = User.objects.filter(role='member', is_verified=True).count()
    new_this_month = User.objects.filter(
        role='member',
        created_at__year=today.year,
        created_at__month=today.month,
    ).count()
    expiring = Membership.objects.filter(
        status='active',
        expiry_date__lte=week_ahead,
    ).count()
    ltv_total = Membership.objects.aggregate(t=Sum('lifetime_value'))['t'] or 0

    return Response({
        'total': total,
        'active': active,
        'verified': verified,
        'new_this_month': new_this_month,
        'expiring_soon': expiring,
        'total_ltv': float(ltv_total),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def member_action(request, user_id):
    """
    POST /api/admin/members/<id>/action/
    Body: { "action": "freeze"|"renew"|"delete"|"message", "payload": {...} }
    """
    try:
        u = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'Member not found.'}, status=404)

    action = request.data.get('action')

    if action == 'freeze':
        membership = getattr(u, 'membership', None)
        if membership:
            membership.is_frozen = True
            membership.status = 'frozen'
            membership.frozen_until = timezone.localdate() + timedelta(days=30)
            membership.save()
        return Response({'detail': 'Membership frozen.', 'member_id': u.id})

    if action == 'renew':
        membership = getattr(u, 'membership', None)
        if membership:
            membership.expiry_date = membership.expiry_date + timedelta(days=365)
            membership.status = 'active'
            membership.is_frozen = False
            membership.save()
        return Response({'detail': 'Membership renewed.', 'member_id': u.id})

    if action == 'delete':
        u.is_active = False
        u.save()
        return Response({'detail': 'Member deactivated.', 'member_id': u.id})

    if action == 'message':
        payload = request.data.get('payload', {})
        return Response({
            'detail': 'Message queued.',
            'member_id': u.id,
            'message': payload.get('message', ''),
        })

    return Response({'detail': f'Unknown action: {action}'}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def bulk_member_action(request):
    """
    POST /api/admin/members/bulk-action/
    Body: { "action": "freeze"|"message"|"export", "member_ids": [1,2,3] }
    """
    action = request.data.get('action')
    member_ids = request.data.get('member_ids', [])

    if not isinstance(member_ids, list) or not member_ids:
        return Response({'detail': 'member_ids must be a non-empty list.'}, status=400)

    users = User.objects.filter(id__in=member_ids, role='member')
    affected = users.count()

    if action == 'freeze':
        Membership.objects.filter(member__in=users).update(
            is_frozen=True, status='frozen',
        )
        return Response({'detail': f'{affected} memberships frozen.', 'count': affected})

    if action == 'message':
        return Response({'detail': f'{affected} messages queued.', 'count': affected})

    if action == 'export':
        def full_name(u):
            if hasattr(u, 'full_name') and u.full_name:
                return u.full_name
            return f"{u.first_name} {u.last_name}".strip() or u.email

        rows = [
            {'id': u.id, 'email': u.email, 'name': full_name(u),
             'role': u.role, 'is_active': u.is_active}
            for u in users
        ]
        return Response({'detail': 'Export ready.', 'count': affected, 'rows': rows})

    return Response({'detail': f'Unknown action: {action}'}, status=400)


# ============================================
# MACHINES ADMIN
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def machines_list(request):
    """
    GET /api/admin/machines/
    """
    qs = Exercise.objects.filter(is_active=True)

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)

    data = [{
        'id': ex.id,
        'name': ex.name,
        'category': ex.category,
        'primary_muscle': ex.primary_muscle,
        'machine_id': ex.machine_id,
        'qr_tag_id': ex.qr_tag_id,
        'is_active': ex.is_active,
        'total_workout_entries': ex.workout_entries.count(),
    } for ex in qs[:100]]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def machine_stats(request):
    """
    GET /api/admin/machines/stats/
    """
    total = Exercise.objects.filter(is_active=True).count()
    with_qr = Exercise.objects.filter(
        is_active=True
    ).exclude(qr_tag_id='').exclude(qr_tag_id__isnull=True).count()
    without_qr = total - with_qr

    top = (
        Exercise.objects.filter(is_active=True)
        .annotate(entry_count=Count('workout_entries'))
        .order_by('-entry_count')
        .first()
    )

    return Response({
        'total': total,
        'with_qr': with_qr,
        'without_qr': without_qr,
        'top_machine': top.name if top else None,
        'top_machine_count': top.entry_count if top else 0,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def machine_categories(request):
    """
    GET /api/admin/machines/categories/
    """
    cats = (
        Exercise.objects.filter(is_active=True)
        .values_list('category', flat=True)
        .distinct()
    )
    return Response([c for c in cats if c])


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def regenerate_qr(request, exercise_id):
    """
    POST /api/admin/machines/<id>/regenerate-qr/
    """
    import uuid

    try:
        ex = Exercise.objects.get(id=exercise_id)
    except Exercise.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    ex.qr_tag_id = f"TITAN-MCH-{uuid.uuid4().hex[:4].upper()}"
    ex.save()

    return Response({'id': ex.id, 'qr_tag_id': ex.qr_tag_id})


# ============================================
# FINANCE ADMIN
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def finance_overview(request):
    """
    GET /api/admin/finance/overview/
    """
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    this_month = Transaction.objects.filter(
        status='settled',
        created_at__year=now.year,
        created_at__month=now.month,
    )
    mrr = this_month.aggregate(t=Sum('amount'))['t'] or 0

    recent = Transaction.objects.filter(status='settled', created_at__gte=thirty_days_ago)
    revenue_30d = recent.aggregate(t=Sum('amount'))['t'] or 0

    pending = Transaction.objects.filter(status='pending')
    pending_amount = pending.aggregate(t=Sum('amount'))['t'] or 0

    refunds_30d = Transaction.objects.filter(
        status='refunded',
        created_at__gte=thirty_days_ago,
    ).aggregate(t=Sum('amount'))['t'] or 0

    return Response({
        'mrr': float(mrr),
        'arr': float(mrr) * 12,
        'last_30d': float(revenue_30d),
        'pending_amount': float(pending_amount),
        'pending_count': pending.count(),
        'refunds_30d': float(abs(refunds_30d)),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def transactions_list(request):
    """
    GET /api/admin/finance/transactions/
    """
    qs = Transaction.objects.select_related('member').all()

    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    try:
        page = int(request.query_params.get('page', 1))
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
    except ValueError:
        start, end = 0, 20
        page = 1

    def full_name(u):
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        return f"{u.first_name} {u.last_name}".strip() or u.email

    data = [{
        'id': t.id,
        'transaction_id': t.transaction_id,
        'member_email': t.member.email,
        'member_name': full_name(t.member),
        'description': t.description,
        'amount': float(t.amount),
        'status': t.status,
        'created_at': t.created_at,
    } for t in qs[start:end]]

    return Response({
        'results': data,
        'total': qs.count(),
        'page': page,
    })


# ============================================
# FLOW + REVENUE (dashboard)
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def flow_and_revenue(request):
    """
    GET /api/admin/flow-and-revenue/
    """
    from django.db.models.functions import ExtractHour

    today = timezone.localdate()

    today_hours = (
        CheckIn.objects
        .filter(check_in_time__date=today)
        .annotate(hour=ExtractHour('check_in_time'))
        .values('hour')
        .annotate(count=Count('id'))
    )
    today_map = {row['hour']: row['count'] for row in today_hours}
    today_curve = [{'hour': h, 'count': today_map.get(h, 0)} for h in range(24)]

    thirty_days_ago = today - timedelta(days=30)
    avg_rows = (
        CheckIn.objects
        .filter(check_in_time__date__gte=thirty_days_ago,
                check_in_time__date__lt=today)
        .annotate(hour=ExtractHour('check_in_time'))
        .values('hour')
        .annotate(count=Count('id'))
    )
    avg_map = {row['hour']: row['count'] / 30 for row in avg_rows}
    avg_curve = [
        {'hour': h, 'count': round(avg_map.get(h, 0), 1)}
        for h in range(24)
    ]

    thirty_days_ago_dt = timezone.now() - timedelta(days=30)
    recent = Transaction.objects.filter(
        status='settled', created_at__gte=thirty_days_ago_dt,
    )

    streams_qs = recent.values('description').annotate(
        total=Sum('amount'), count=Count('id'),
    )

    def bucket(desc):
        if not desc:
            return 'Other'
        d = desc.lower()
        if 'membership' in d or 'plan' in d or 'tier' in d:
            return 'Memberships'
        if 'course' in d or 'class' in d or 'training' in d:
            return 'Courses'
        if 'shop' in d or 'product' in d or 'order' in d:
            return 'Shop'
        if 'nutrition' in d or 'diet' in d:
            return 'Nutrition'
        if 'locker' in d or 'facility' in d or 'day pass' in d:
            return 'Facility'
        return 'Other'

    buckets = {}
    for row in streams_qs:
        key = bucket(row['description'])
        buckets[key] = buckets.get(key, 0) + float(row['total'])

    total_revenue = sum(buckets.values()) or 1

    REVENUE_COLORS = {
        'Memberships': 'bg-primary-container',
        'Courses': 'bg-primary',
        'Shop': 'bg-emerald-400',
        'Nutrition': 'bg-blue-400',
        'Facility': 'bg-amber-400',
        'Other': 'bg-surface-variant',
    }

    revenue_streams = [
        {
            'label': k,
            'value': round(v, 2),
            'percent': round((v / total_revenue) * 100, 1),
            'color': REVENUE_COLORS.get(k, 'bg-surface-variant'),
        }
        for k, v in sorted(buckets.items(), key=lambda x: -x[1])
    ]

    arr = total_revenue * 12
    total_members = User.objects.filter(role='member').count() or 1

    return Response({
        'flow': {
            'today': today_curve,
            'rolling_mean': avg_curve,
        },
        'revenue_streams': revenue_streams,
        'summary': {
            'total_30d': round(total_revenue, 2),
            'arr': round(arr, 2),
            'avg_per_member': round(total_revenue / total_members, 2),
        },
    })


# ============================================
# ARENA HEATMAP
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def arena_heatmap(request):
    """
    GET /api/admin/arena-heatmap/
    """
    today = timezone.localdate()

    rows = (
        CheckIn.objects
        .filter(check_in_time__date=today)
        .values('facility', 'zone')
        .annotate(count=Count('id'), avg_duration=Avg('duration_minutes'))
    )

    active_now = CheckIn.objects.filter(
        check_in_time__date=today, check_out_time__isnull=True
    ).count()

    total_today = sum(r['count'] for r in rows) or 1

    ZONE_ICONS = {
        'Strength Arena': 'fitness_center',
        'Cardio Deck': 'directions_run',
        'Functional Rig': 'sports_gymnastics',
        'Free Weights': 'weight',
        'Studio': 'self_improvement',
        'Locker Room': 'lock',
        'Recovery Zone': 'spa',
    }

    zones = []
    for i, r in enumerate(rows):
        zone_name = r['zone'] or r['facility'] or 'General Floor'
        load = round((r['count'] / total_today) * 100, 1)

        if load >= 85:
            sector_label = 'CRITICAL'
            bar_color = 'bg-error'
            sector_label_accent = True
        elif load >= 60:
            sector_label = 'ELEVATED'
            bar_color = 'bg-primary'
            sector_label_accent = False
        else:
            sector_label = 'NOMINAL'
            bar_color = 'bg-emerald-400'
            sector_label_accent = False

        avg_dur = int(r['avg_duration'] or 0)

        zones.append({
            'sector': f'SECTOR-{i+1:02d}',
            'sectorLabel': sector_label,
            'title': zone_name,
            'description': f"{r['count']} entries today",
            'load': f'{int(load)}%',
            'width': min(100, load),
            'barColor': bar_color,
            'dwell': f'Avg {avg_dur} min',
            'footerLeft': r['facility'],
            'footerRight': f'{r["count"]} visits',
            'icon': ZONE_ICONS.get(zone_name, 'meeting_room'),
            'topBar': bar_color,
            'sectorAccent': load >= 85,
            'sectorLabelAccent': sector_label_accent,
            'footerRightAccent': 'error' if load >= 85 else 'primary' if load >= 60 else 'none',
        })

    return Response({
        'zones': zones,
        'active_now': active_now,
        'total_today': total_today,
    })


# ============================================
# AUDIT FEED
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def audit_feed(request):
    """
    GET /api/admin/audit-feed/
    """
    limit = int(request.query_params.get('limit', 20))
    events = []

    for c in CheckIn.objects.select_related('member').order_by('-check_in_time')[:10]:
        events.append({
            'time': c.check_in_time.strftime('%H:%M:%S'),
            'timestamp': c.check_in_time,
            'node': c.zone or c.facility,
            'event': f'{c.member.email} checked in',
            'detail': f'Facility: {c.facility}',
            'status': 'ENTRY',
            'statusType': 'ok',
            'isAlert': False,
        })

    for t in Transaction.objects.select_related('member').order_by('-created_at')[:10]:
        events.append({
            'time': t.created_at.strftime('%H:%M:%S'),
            'timestamp': t.created_at,
            'node': 'PAYMENT GATEWAY',
            'event': t.description,
            'detail': f'{t.member.email} — ${float(t.amount):.2f}',
            'status': t.status.upper(),
            'statusType': 'ok' if t.status == 'settled' else 'default',
            'isAlert': t.status != 'settled',
        })

    for o in Order.objects.select_related('member').order_by('-created_at')[:5]:
        events.append({
            'time': o.created_at.strftime('%H:%M:%S'),
            'timestamp': o.created_at,
            'node': 'SHOP ORDER',
            'event': f'Order {o.order_number}',
            'detail': f'{o.member.email} — ${float(o.total):.2f}',
            'status': o.status.upper(),
            'statusType': 'ok' if o.status in ('paid', 'completed') else 'default',
            'isAlert': o.status in ('cancelled', 'refunded'),
        })

    events.sort(key=lambda x: x['timestamp'], reverse=True)

    for e in events:
        e['timestamp'] = e['timestamp'].isoformat()

    return Response(events[:limit])


# ============================================
# FACILITY NODES
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def facility_nodes(request):
    """
    GET /api/admin/facility-nodes/
    """
    today = timezone.localdate()

    facilities = (
        CheckIn.objects
        .filter(check_in_time__date=today)
        .values('facility')
        .annotate(
            visits_today=Count('id'),
            active_now=Count('id', filter=Q(check_out_time__isnull=True)),
        )
    )

    nodes = []
    for f in facilities:
        load = f['active_now']
        status = 'optimal' if load < 20 else 'elevated' if load < 50 else 'congested'

        nodes.append({
            'name': f['facility'],
            'active_now': load,
            'visits_today': f['visits_today'],
            'status': status,
            'capacity': 80,
            'utilization': round((load / 80) * 100, 1) if load else 0,
        })

    if not nodes:
        nodes.append({
            'name': 'Metro Station Core 01',
            'active_now': 0,
            'visits_today': 0,
            'status': 'optimal',
            'capacity': 80,
            'utilization': 0,
        })

    return Response(nodes)


# ============================================
# ANALYTICS
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def analytics_kpis(request):
    """
    GET /api/admin/analytics/kpis/
    """
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    total_members = User.objects.filter(role='member').count()
    new_members_30d = User.objects.filter(role='member', created_at__gte=thirty_days_ago).count()

    avg_duration = Workout.objects.filter(
        status='completed'
    ).aggregate(a=Avg('duration_minutes'))['a'] or 0

    active_members = Membership.objects.filter(status='active').count()
    retention = (active_members / total_members * 100) if total_members > 0 else 0

    return Response({
        'total_members': total_members,
        'new_members_30d': new_members_30d,
        'avg_session_minutes': round(avg_duration, 1),
        'retention_rate': round(retention, 1),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def analytics_growth(request):
    """
    GET /api/admin/analytics/growth/
    """
    from django.db.models.functions import TruncMonth

    data = (
        User.objects.filter(role='member')
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')[:12]
    )

    return Response([{
        'month': item['month'].strftime('%b %Y'),
        'new_members': item['count'],
    } for item in data])


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def ai_insights(request):
    """
    GET /api/admin/analytics/insights/
    """
    insights = []

    pending_courses = Course.objects.filter(status='pending').count()
    if pending_courses > 0:
        insights.append({
            'priority': 'high',
            'icon': 'school',
            'title': f'{pending_courses} Course(s) Awaiting Approval',
            'description': 'Trainers have submitted new courses that need review.',
            'action': 'Review Courses',
        })

    soon = timezone.localdate() + timedelta(days=7)
    expiring = Membership.objects.filter(
        status='active', expiry_date__lte=soon
    ).count()
    if expiring > 0:
        insights.append({
            'priority': 'high',
            'icon': 'schedule',
            'title': f'{expiring} Memberships Expiring This Week',
            'description': 'Reach out with renewal offers to prevent churn.',
            'action': 'View Members',
        })

    low_stock = Product.objects.filter(
        stock_quantity__lte=5, is_active=True
    ).count()
    if low_stock > 0:
        insights.append({
            'priority': 'medium',
            'icon': 'inventory',
            'title': f'{low_stock} Products Low on Stock',
            'description': 'Reorder before items run out.',
            'action': 'View Shop',
        })

    return Response(insights)

    # apps/admin_api/views.py — ADD AT BOTTOM

# ============================================
# REVENUE MONTHLY (for chart)
# ============================================
# apps/admin_api/views.py — REPLACE the revenue_monthly function

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def revenue_monthly(request):
    """
    GET /api/admin/finance/revenue-monthly/?months=12
    """
    from django.db.models.functions import TruncMonth
    from datetime import date

    try:
        months = int(request.query_params.get('months', 12))
        months = max(1, min(months, 24))
    except (TypeError, ValueError):
        months = 12

    data = (
        Transaction.objects
        .filter(status='settled')
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(revenue=Sum('amount'))
        .order_by('month')
    )

    by_month = {}
    for item in data:
        if item['month']:
            key = item['month'].strftime('%Y-%m')
            by_month[key] = float(item['revenue'] or 0)

    # Build the last N months manually (no dateutil)
    today = date.today()
    result = []
    for i in range(months - 1, -1, -1):
        # Walk back i months
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        key = f"{year:04d}-{month:02d}"
        rev = by_month.get(key, 0)
        target = rev * 1.1 if rev else 100000

        # Month name
        month_names = ['Jan','Feb','Mar','Apr','May','Jun',
                       'Jul','Aug','Sep','Oct','Nov','Dec']
        full = f"{month_names[month - 1]} {year}"
        short = month_names[month - 1]

        result.append({
            'month': full,
            'short': short,
            'revenue': round(rev, 2),
            'target': round(target, 2),
        })

    return Response(result)

# ============================================
# REVENUE STREAMS (breakdown)
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def revenue_streams_view(request):
    """
    GET /api/admin/finance/revenue-streams/
    Returns breakdown by revenue source + payment methods.
    """
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent = Transaction.objects.filter(status='settled', created_at__gte=thirty_days_ago)

    # By description → bucket
    def bucket(desc):
        if not desc:
            return 'Other'
        d = desc.lower()
        if 'membership' in d or 'plan' in d or 'tier' in d:
            return 'Memberships'
        if 'course' in d or 'class' in d or 'training' in d:
            return 'Courses'
        if 'shop' in d or 'product' in d or 'order' in d:
            return 'Shop'
        if 'nutrition' in d or 'diet' in d:
            return 'Nutrition'
        if 'locker' in d or 'facility' in d or 'day pass' in d:
            return 'Facility'
        return 'Other'

    rows = recent.values('description').annotate(total=Sum('amount'))
    buckets = {}
    for row in rows:
        k = bucket(row['description'])
        buckets[k] = buckets.get(k, 0) + float(row['total'])

    total = sum(buckets.values()) or 1

    ICONS = {
        'Memberships': 'card_membership',
        'Courses': 'school',
        'Shop': 'shopping_bag',
        'Nutrition': 'restaurant',
        'Facility': 'meeting_room',
        'Other': 'receipt_long',
    }
    COLORS = {
        'Memberships': 'bg-primary-container',
        'Courses': 'bg-primary',
        'Shop': 'bg-emerald-400',
        'Nutrition': 'bg-blue-400',
        'Facility': 'bg-amber-400',
        'Other': 'bg-surface-variant',
    }

    streams = [
        {
            'label': k,
            'value': round(v, 2),
            'percent': round((v / total) * 100, 1),
            'icon': ICONS.get(k, 'receipt_long'),
            'color': COLORS.get(k, 'bg-surface-variant'),
        }
        for k, v in sorted(buckets.items(), key=lambda x: -x[1])
    ]

    # Payment methods (from Transaction.method if exists; fallback: derive)
    payment_buckets = {}
    for row in recent.values('description', 'amount'):
        # We don't have a `method` field assumed — bucket by description as fallback
        method = 'Card'
        d = (row['description'] or '').lower()
        if 'cash' in d:
            method = 'Cash'
        elif 'transfer' in d:
            method = 'Bank Transfer'
        elif 'wallet' in d or 'apple' in d or 'google' in d:
            method = 'Wallet'
        payment_buckets[method] = payment_buckets.get(method, 0) + float(row['amount'])

    ptot = sum(payment_buckets.values()) or 1
    PAY_ICONS = {
        'Card': 'credit_card',
        'Cash': 'payments',
        'Bank Transfer': 'account_balance',
        'Wallet': 'account_balance_wallet',
    }

    payment_methods = [
        {
            'label': k,
            'value': round(v, 2),
            'percent': round((v / ptot) * 100, 1),
            'icon': PAY_ICONS.get(k, 'credit_card'),
        }
        for k, v in sorted(payment_buckets.items(), key=lambda x: -x[1])
    ]

    return Response({
        'streams': streams,
        'payment_methods': payment_methods,
        'total_30d': round(sum(buckets.values()), 2),
    })


# ============================================
# TOP MEMBERS (by LTV)
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def top_members_view(request):
    """
    GET /api/admin/finance/top-members/?limit=5
    """
    try:
        limit = int(request.query_params.get('limit', 5))
    except ValueError:
        limit = 5

    memberships = (
        Membership.objects
        .select_related('member', 'plan')
        .order_by('-lifetime_value')[:limit]
    )

    def full_name(u):
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def initials(u):
        name = full_name(u)
        parts = name.split(' ')
        return ''.join(p[0] for p in parts[:2]).upper() or '?'

    data = []
    for idx, m in enumerate(memberships, start=1):
        data.append({
            'rank': idx,
            'id': m.member.id,
            'name': full_name(m.member),
            'initials': initials(m.member),
            'tier': m.plan.display_name if m.plan else 'Basic',
            'ltv': float(m.lifetime_value),
        })

    total_ltv = sum(d['ltv'] for d in data)

    return Response({
        'members': data,
        'total_ltv': total_ltv,
    })


# ============================================
# TRANSACTION DETAIL (for InvoiceDrawer)
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def transaction_detail(request, transaction_id):
    """
    GET /api/admin/finance/transactions/<id>/
    """
    try:
        t = Transaction.objects.select_related('member').get(id=transaction_id)
    except Transaction.DoesNotExist:
        return Response({'detail': 'Transaction not found.'}, status=404)

    def full_name(u):
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        return f"{u.first_name} {u.last_name}".strip() or u.email

    return Response({
        'id': t.id,
        'transaction_id': t.transaction_id,
        'member': full_name(t.member),
        'member_email': t.member.email,
        'member_id': t.member.id,
        'description': t.description,
        'amount': float(t.amount),
        'status': t.status,
        'type': getattr(t, 'type', 'payment'),
        'method': getattr(t, 'method', 'Card'),
        'created_at': t.created_at,
    })

    # apps/admin_api/views.py — ADD AT BOTTOM

# ============================================
# TRAINERS
# ============================================
# apps/admin_api/views.py — REPLACE both functions

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def trainers_list_admin(request):
    """
    GET /api/admin/trainers/
    """
    try:
        from apps.catalog.models import TrainerProfile
    except ImportError:
        return Response([])

    qs = TrainerProfile.objects.select_related('user').all()

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(title__icontains=search)
        )

    if request.query_params.get('verified') == 'true':
        qs = qs.filter(is_verified=True)

    def full_name(u):
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def initials(u):
        name = full_name(u)
        parts = name.split(' ')
        return ''.join(p[0] for p in parts[:2]).upper() or '?'

    data = []
    for t in qs:
        # Use getattr with defaults — never crash on missing field
        data.append({
            'id': t.id,
            'user_id': t.user.id,
            'user_name': full_name(t.user),
            'user_email': t.user.email,
            'initials': initials(t.user),
            'title': getattr(t, 'title', '') or 'Trainer',
            'credentials': getattr(t, 'credentials', '') or '',
            'bio': getattr(t, 'bio', '') or '',
            'specialties': getattr(t, 'specialties', None) or [],
            'rating': float(getattr(t, 'rating', 0) or 0),
            'total_reviews': getattr(t, 'total_reviews', 0) or 0,
            'total_clients': getattr(t, 'total_clients', 0) or 0,
            'years_experience': getattr(t, 'years_experience', 0) or 0,
            'hourly_rate': float(getattr(t, 'hourly_rate', 0) or 0),
            'is_verified': getattr(t, 'is_verified', False),
            'is_accepting_clients': getattr(t, 'is_accepting_clients', True),
        })

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def trainer_stats_admin(request):
    """
    GET /api/admin/trainers/stats/
    """
    try:
        from apps.catalog.models import TrainerProfile
    except ImportError:
        return Response({
            'total': 0, 'verified': 0, 'accepting': 0, 'avg_rating': 0,
        })

    total = TrainerProfile.objects.count()
    verified = TrainerProfile.objects.filter(is_verified=True).count() \
        if hasattr(TrainerProfile, 'is_verified') else 0
    accepting = TrainerProfile.objects.filter(is_accepting_clients=True).count() \
        if hasattr(TrainerProfile, 'is_accepting_clients') else 0

    avg = TrainerProfile.objects.aggregate(a=Avg('rating'))['a'] \
        if hasattr(TrainerProfile, 'rating') else 0

    return Response({
        'total': total,
        'verified': verified,
        'accepting': accepting,
        'avg_rating': round(float(avg or 0), 2),
    })
# ============================================
# STAFF
# ============================================
# apps/admin_api/views.py — REPLACE staff_list_admin and staff_stats_admin

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def staff_list_admin(request):
    """
    GET /api/admin/staff/
    """
    STAFF_ROLES = ['admin', 'manager', 'trainer', 'nutritionist', 'receptionist']

    qs = User.objects.filter(role__in=STAFF_ROLES).order_by('-created_at')

    role = request.query_params.get('role')
    if role and role != 'all':
        qs = qs.filter(role=role)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )

    def full_name(u):
        if hasattr(u, 'full_name') and u.full_name:
            return u.full_name
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def initials(u):
        name = full_name(u)
        parts = name.split(' ')
        return ''.join(p[0] for p in parts[:2]).upper() or '?'

    data = [{
        'id': u.id,
        'user_name': full_name(u),
        'user_email': u.email,
        'initials': initials(u),
        'role': u.role,
        'status': 'active' if u.is_active else 'suspended',
        'department': u.role,
        'shift_display': 'Full Time',
        'phone': getattr(u, 'phone', '') or '',
        'created_at': u.created_at,
    } for u in qs]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def staff_stats_admin(request):
    """
    GET /api/admin/staff/stats/
    """
    STAFF_ROLES = ['admin', 'manager', 'trainer', 'nutritionist', 'receptionist']

    total = User.objects.filter(role__in=STAFF_ROLES).count()
    active = User.objects.filter(role__in=STAFF_ROLES, is_active=True).count()

    return Response({
        'total': total,
        'on_shift_now': active,
        'avg_tenure_years': 2,
        'open_positions': 0,
    })

    # apps/admin_api/views.py — ADD AT BOTTOM

from .models import SystemSettings


# ============================================
# SYSTEM SETTINGS
# ============================================
DEFAULT_SETTINGS = {
    'general': {
        'gym_name': 'Smart Gym HQ Metro',
        'primary_email': 'contact@smartgym.com',
        'support_phone': '+1 (555) 010-4832',
        'address': 'Metro Station Core 01 · Sub-Level Alpha',
        'language': 'English (US)',
        'timezone': 'GMT-05:00 EST',
        'currency': 'USD ($)',
    },
    'roles': {
        'matrix': [
            {'role': 'Super Admin', 'members': 'Full', 'trainers': 'Full', 'finance': 'Full', 'machines': 'Full', 'settings': 'Full'},
            {'role': 'Manager', 'members': 'Edit', 'trainers': 'Edit', 'finance': 'Read', 'machines': 'Edit', 'settings': 'None'},
            {'role': 'Trainer', 'members': 'Read', 'trainers': 'Edit', 'finance': 'None', 'machines': 'Read', 'settings': 'None'},
            {'role': 'Receptionist', 'members': 'Edit', 'trainers': 'Read', 'finance': 'None', 'machines': 'Read', 'settings': 'None'},
        ]
    },
    'integrations': {
        'services': [
            {'name': 'Stripe Payments', 'detail': 'Primary processor', 'icon': 'credit_card', 'status': 'connected'},
            {'name': 'Twilio SMS', 'detail': 'Member notifications', 'icon': 'sms', 'status': 'connected'},
            {'name': 'Apple HealthKit', 'detail': 'Workout sync', 'icon': 'favorite', 'status': 'review'},
            {'name': 'Google Fit', 'detail': 'Activity telemetry', 'icon': 'fitness_center', 'status': 'review'},
        ]
    },
    'security': {
        'enforce_2fa_admins': True,
        'enforce_2fa_staff': False,
        'biometric_login': True,
        'session_timeout_30min': True,
        'ip_whitelist_admin': False,
        'audit_log_retention': True,
    },
    'notifications': {
        'push': True,
        'email': True,
        'whatsapp': True,
        'sms': False,
        'marketing_newsletter': True,
    },
    'billing': {
        'currency': 'USD ($)',
        'tax_rate': 5.0,
        'invoice_prefix': 'INV-2026-',
        'payment_terms_days': 30,
        'auto_charge_renewals': True,
        'allow_refunds': True,
        'invoice_pdf_branding': True,
    },
}


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def system_settings_get(request):
    """
    GET /api/admin/settings/
    Returns all settings sections.
    """
    obj = SystemSettings.get_solo()

    # Merge saved values with defaults (so new keys appear)
    result = {}
    for section, default_val in DEFAULT_SETTINGS.items():
        saved = getattr(obj, section, None) or {}
        if isinstance(default_val, dict) and isinstance(saved, dict):
            merged = {**default_val, **saved}
        else:
            merged = saved or default_val
        result[section] = merged

    return Response(result)


@api_view(['PATCH', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def system_settings_update(request):
    """
    PATCH /api/admin/settings/
    Body: { "general": {...}, "security": {...}, ... }  ← partial OK
    """
    obj = SystemSettings.get_solo()

    allowed_sections = list(DEFAULT_SETTINGS.keys())

    for section in allowed_sections:
        if section in request.data:
            incoming = request.data[section]
            if not isinstance(incoming, dict):
                return Response(
                    {'detail': f'{section} must be an object.'},
                    status=400,
                )
            existing = getattr(obj, section, None) or {}
            merged = {**existing, **incoming}
            setattr(obj, section, merged)

    obj.updated_by = request.user
    obj.save()

    # Return merged with defaults
    return system_settings_get(request)