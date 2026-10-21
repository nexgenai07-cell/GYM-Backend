"""
Live gym occupancy from real check-ins: members checked in and not yet
checked out (ignoring sessions left open for more than STALE_HOURS).
Capacity is GYM_CAPACITY (settings / env) or, if unset, the sum of the
active facilities' capacities.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone

STALE_HOURS = 6


def _capacity():
    configured = getattr(settings, 'GYM_CAPACITY', 0)
    if configured:
        return int(configured)
    from apps.facilities.models import Facility
    return Facility.objects.filter(is_active=True).aggregate(c=Sum('capacity'))['c'] or 0


def _label(percent):
    if percent >= 85:
        return 'Very busy'
    if percent >= 60:
        return 'Busy'
    if percent >= 30:
        return 'Moderate'
    return 'Quiet'


def peak_window(days=30):
    """'17:00 – 20:00'-style busiest 3-hour window over the last `days`, or None."""
    from apps.members.models import CheckIn
    buckets = [0] * 24
    since = timezone.now() - timedelta(days=days)
    for t in CheckIn.objects.filter(check_in_time__gte=since).values_list('check_in_time', flat=True):
        buckets[timezone.localtime(t).hour] += 1
    if not any(buckets):
        return None
    start = max(range(22), key=lambda h: sum(buckets[h:h + 3]))
    return f'{start:02d}:00 – {start + 3:02d}:00'


def current_occupancy():
    from apps.members.models import CheckIn
    open_qs = CheckIn.objects.filter(
        check_out_time__isnull=True,
        check_in_time__gte=timezone.now() - timedelta(hours=STALE_HOURS),
    )
    current = open_qs.count()
    capacity = _capacity()
    percent = min(100, round(100 * current / capacity)) if capacity else 0
    zones = [
        {'label': z['zone'] or z['facility'], 'count': z['n'],
         'percent': min(100, round(100 * z['n'] / current)) if current else 0}
        for z in open_qs.values('zone', 'facility').annotate(n=Count('id')).order_by('-n')[:4]
    ]
    return {
        'current': current,
        'capacity': capacity,
        'percent': percent,
        'label': _label(percent) if capacity else ('Open' if current else 'Quiet'),
        'zones': zones,
        'peak_window': peak_window(),
    }
