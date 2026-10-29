"""
Paid classes. A class with a price is locked until the member pays for it, either:
  · the whole class — every session from today to the class's last day (ends_on), or
  · one session — a single date.
Free classes work as before (a standing weekly spot). The price is set on the class
(price_per_session; full_price for the whole run, or per-session × sessions left when empty).
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from .models import ClassEnrollment, ClassPass

BOOKED = ['enrolled', 'attended']
SESSION_WEEKS_AHEAD = 4        # single sessions can be bought up to 4 weeks ahead


def is_paid(c):
    return (c.price_per_session or 0) > 0 or (c.full_price or 0) > 0


def has_ended(c, today=None):
    return bool(c.ends_on and c.ends_on < (today or timezone.localdate()))


def _started(c, d):
    """True once the session on date d has begun (gym time)."""
    now = timezone.localtime()
    start = timezone.make_aware(datetime.combine(d, c.start_time), timezone.get_current_timezone())
    return start <= now


def session_dates(c, until=None, today=None):
    """Dates the class still runs on, from today (sessions not started yet) to `until` / its last day."""
    today = today or timezone.localdate()
    first = max(today, c.starts_on) if c.starts_on else today
    last = min(d for d in (until, c.ends_on) if d) if (until or c.ends_on) else first + timedelta(weeks=SESSION_WEEKS_AHEAD)
    d = first + timedelta(days=(c.day_of_week - first.weekday()) % 7)
    out = []
    while d <= last:
        if not _started(c, d):
            out.append(d)
        d += timedelta(days=7)
    return out


def bookable_dates(c, today=None):
    """Single sessions on sale: the next few weeks, within the class's run."""
    today = today or timezone.localdate()
    return session_dates(c, until=today + timedelta(weeks=SESSION_WEEKS_AHEAD), today=today)


def full_offer(c, today=None):
    """{price, sessions, until} for buying the rest of the class, or None (no end date / nothing left)."""
    if not c.ends_on or has_ended(c, today):
        return None
    dates = session_dates(c, today=today)
    if not dates:
        return None
    price = c.full_price if (c.full_price or 0) > 0 else (c.price_per_session or 0) * len(dates)
    if price <= 0:
        return None
    return {'price': Decimal(price).quantize(Decimal('0.01')), 'sessions': len(dates), 'until': c.ends_on,
            'from': dates[0]}


def booked_on(c, d):
    """Spots taken on date d: standing spots (whole-class passes / free bookings) + single-session passes."""
    standing = c.enrollments.filter(status__in=BOOKED).count()
    singles = ClassPass.objects.filter(gym_class=c, kind='session', session_date=d, is_cancelled=False).count()
    return standing + singles


def member_access(member, c, today=None):
    """{'full': until | None, 'sessions': [dates]} — what the member has paid for."""
    today = today or timezone.localdate()
    passes = ClassPass.objects.filter(gym_class=c, member=member, is_cancelled=False, valid_until__gte=today)
    full = next((p.valid_until for p in passes if p.kind == 'full'), None)
    return {'full': full, 'sessions': sorted(p.session_date for p in passes if p.kind == 'session')}


def check_purchase(member, c, kind, day=None):
    """(price, valid_until) for a pass the member may buy now, or raises ValueError with the reason."""
    today = timezone.localdate()
    if not c.is_active or has_ended(c, today):
        raise ValueError('This class isn’t running any more.')
    if not is_paid(c):
        raise ValueError('This class is free — book it directly.')
    ms = getattr(member, 'membership', None)
    if ms is None or not ms.allows_entry:
        raise ValueError('You need an active membership to join classes.')
    mine = member_access(member, c, today)
    if mine['full'] or ClassEnrollment.objects.filter(gym_class=c, member=member, status__in=BOOKED).exists():
        raise ValueError('You already have a spot in this class.')
    if kind == 'full':
        offer = full_offer(c, today)
        if offer is None:
            raise ValueError('This class can only be paid per session.')
        if any(booked_on(c, d) >= c.capacity for d in session_dates(c, today=today)):
            raise ValueError('The class is full on some of its dates — buy single sessions on the days with space.')
        return offer['price'], c.ends_on
    if kind == 'session':
        if (c.price_per_session or 0) <= 0:
            raise ValueError('This class is sold as a whole class only.')
        if day not in bookable_dates(c, today):
            raise ValueError('Pick one of the upcoming dates for this class.')
        if day in mine['sessions']:
            raise ValueError('You already paid for this session.')
        if booked_on(c, day) >= c.capacity:
            raise ValueError('That session is full — pick another date.')
        return Decimal(c.price_per_session).quantize(Decimal('0.01')), day
    raise ValueError('Choose the whole class or a single session.')


def parse_day(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
