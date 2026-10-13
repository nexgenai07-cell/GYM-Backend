# apps/classes/views.py — REPLACE COMPLETELY

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q

from .models import GymClass, ClassEnrollment
from apps.admin_api.permissions import IsAdminUser


def _user_full_name(u):
    """Defensive full_name getter."""
    if u is None:
        return '—'
    if hasattr(u, 'full_name') and u.full_name:
        return u.full_name
    name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
    return name or u.email


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def classes_schedule(request):
    """
    GET /api/classes/schedule/
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    slots_map = {}

    qs = (
        GymClass.objects
        .filter(is_active=True)
        .select_related('trainer__user')
    )

    for cls in qs:
        time_key = cls.start_time.strftime('%H:%M')
        if time_key not in slots_map:
            slots_map[time_key] = {'time': time_key}

        enrolled = cls.enrollments.filter(
            status__in=['enrolled', 'attended']
        ).count()
        status = 'full' if enrolled >= cls.capacity else 'open'

        day_name = (
            days[cls.day_of_week]
            if 0 <= cls.day_of_week < len(days)
            else 'Saturday'
        )

        trainer_name = '—'
        if cls.trainer and cls.trainer.user:
            trainer_name = _user_full_name(cls.trainer.user)

        slots_map[time_key][day_name] = {
            'id': cls.id,
            'name': cls.name,
            'trainer': trainer_name,
            'enrolled': enrolled,
            'capacity': cls.capacity,
            'status': status,
            'category': cls.category,
        }

    for time_key, slot in slots_map.items():
        for day in days:
            if day not in slot:
                slot[day] = {
                    'name': '—',
                    'trainer': '',
                    'enrolled': 0,
                    'capacity': 0,
                    'status': 'open',
                }

    slots = sorted(slots_map.values(), key=lambda x: x['time'])

    return Response({
        'days': days,
        'slots': slots,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def classes_stats(request):
    """
    GET /api/classes/stats/
    """
    total_classes = GymClass.objects.filter(is_active=True).count()
    total_enrolled = ClassEnrollment.objects.filter(
        status__in=['enrolled', 'attended']
    ).count()
    total_waitlisted = ClassEnrollment.objects.filter(status='waitlist').count()

    total_capacity = sum(
        c.capacity for c in GymClass.objects.filter(is_active=True)
    )
    attendance_rate = (
        round((total_enrolled / total_capacity) * 100, 1)
        if total_capacity else 0
    )

    return Response({
        'total_classes': total_classes,
        'active_enrollments': total_enrolled,
        'attendance_rate': attendance_rate,
        'waitlisted': total_waitlisted,
    })