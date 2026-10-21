"""
Bookable 1:1 slots, from the trainer's weekly availability (TrainerAvailability)
minus sessions already booked. A session awaiting payment holds its slot for
HOLD_MINUTES so two members can't pay for the same time.
"""
from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

SLOT_MINUTES = 60
HOLD_MINUTES = 15
MIN_LEAD_MINUTES = 60          # can't book a slot starting within the next hour
MAX_DAYS_AHEAD = 60


def _blocking_sessions(trainer, start, end, exclude_id=None):
    from .models import TrainerSession
    hold_since = timezone.now() - timedelta(minutes=HOLD_MINUTES)
    qs = TrainerSession.objects.filter(
        Q(status='scheduled') | Q(status='pending_payment', created_at__gte=hold_since),
        trainer=trainer, scheduled_at__lt=end,
        scheduled_at__gt=start - timedelta(hours=12),       # sessions are at most a few hours long
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return [s for s in qs if s.scheduled_at + timedelta(minutes=s.duration_minutes) > start]


def slot_is_free(trainer, start, duration_minutes=SLOT_MINUTES, exclude_id=None):
    end = start + timedelta(minutes=duration_minutes)
    return not _blocking_sessions(trainer, start, end, exclude_id)


def within_availability(trainer, start, duration_minutes=SLOT_MINUTES):
    local = timezone.localtime(start)
    end = (local + timedelta(minutes=duration_minutes)).time()
    return trainer.availability.filter(
        is_active=True, day_of_week=local.weekday(),
        start_time__lte=local.time(), end_time__gte=end,
    ).exists() if local.date() == (local + timedelta(minutes=duration_minutes)).date() else False


def available_slots(trainer, day):
    """[{'start': aware datetime, 'label': 'HH:MM'}] for one local date."""
    now = timezone.now()
    if day < timezone.localdate() or day > timezone.localdate() + timedelta(days=MAX_DAYS_AHEAD):
        return []
    tz = timezone.get_current_timezone()
    slots = []
    for window in trainer.availability.filter(is_active=True, day_of_week=day.weekday()).order_by('start_time'):
        start = timezone.make_aware(datetime.combine(day, window.start_time), tz)
        window_end = timezone.make_aware(datetime.combine(day, window.end_time), tz)
        while start + timedelta(minutes=SLOT_MINUTES) <= window_end:
            if start >= now + timedelta(minutes=MIN_LEAD_MINUTES) and slot_is_free(trainer, start):
                slots.append({'start': start, 'label': timezone.localtime(start).strftime('%H:%M')})
            start += timedelta(minutes=SLOT_MINUTES)
    return slots
