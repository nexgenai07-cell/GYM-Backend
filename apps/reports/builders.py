"""
Report builders: each takes (start, end) dates in gym time and returns (header, rows).
Money follows the admin console's rule — locker-credit spending isn't counted twice.
"""
from collections import defaultdict
from datetime import datetime, time

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.admin_api.views import cash_transactions
from apps.catalog.models import Enrollment, TrainerProfile, TrainerSession
from apps.members.models import CheckIn
from apps.payments.models import Transaction
from apps.workouts.models import Exercise


def _bounds(start, end):
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(start, time.min), tz),
            timezone.make_aware(datetime.combine(end, time.max), tz))


def _local(dt):
    return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M') if dt else ''


def _sar(v):
    return f'{float(v or 0):.2f}'


def revenue(start, end):
    lo, hi = _bounds(start, end)
    rows, total = [], 0
    for t in (cash_transactions(Transaction.objects.filter(created_at__range=(lo, hi)))
              .select_related('member').order_by('created_at')):
        total += float(t.amount)
        rows.append([_local(t.created_at), t.transaction_id, t.member.full_name or t.member.email, t.member.email,
                     t.description, t.get_transaction_type_display(), t.payment_method_label, _sar(t.amount)])
    if rows:
        rows.append(['', '', '', '', '', '', 'Total received', _sar(total)])
    return ['Date (gym time)', 'Transaction', 'Member', 'Email', 'Item', 'Type', 'Paid with', 'Amount (SAR)'], rows


def finance(start, end):
    """Money received per month and stream, VAT included in the totals."""
    lo, hi = _bounds(start, end)
    by = defaultdict(lambda: defaultdict(float))
    vat = defaultdict(float)
    for t in cash_transactions(Transaction.objects.filter(created_at__range=(lo, hi))):
        m = timezone.localtime(t.created_at).strftime('%Y-%m')
        by[m][t.get_transaction_type_display()] += float(t.amount)
        vat[m] += float(t.tax_amount or 0)
    streams = sorted({s for m in by.values() for s in m})
    rows = []
    for m in sorted(by):
        rows.append([m, *[_sar(by[m].get(s, 0)) for s in streams], _sar(vat[m]), _sar(sum(by[m].values()))])
    if rows:
        rows.append(['Total', *[_sar(sum(by[m].get(s, 0) for m in by)) for s in streams],
                     _sar(sum(vat.values())), _sar(sum(sum(v.values()) for v in by.values()))])
    return ['Month', *[f'{s} (SAR)' for s in streams], 'VAT included (SAR)', 'Total (SAR)'], rows


def members(start, end):
    """Every member as of today; 'Joined in period' marks sign-ups between the dates."""
    rows = []
    for u in User.objects.filter(role='member').select_related('membership__plan').order_by('first_name'):
        m = getattr(u, 'membership', None)
        joined = timezone.localtime(u.created_at).date()
        rows.append([u.full_name or '', u.email, u.phone or '', m.iqama_number if m else '',
                     m.plan.display_name if m and m.plan_id else '', m.status if m else 'no membership',
                     m.start_date.isoformat() if m and m.start_date else '', m.expiry_date.isoformat() if m and m.expiry_date else '',
                     joined.isoformat(), 'yes' if start <= joined <= end else '', 'yes' if u.is_active else 'no'])
    return ['Name', 'Email', 'Phone', 'Iqama', 'Plan', 'Membership', 'Started', 'Expires', 'Account created',
            'Joined in period', 'Account active'], rows


def attendance(start, end):
    lo, hi = _bounds(start, end)
    rows = [[_local(c.check_in_time), _local(c.check_out_time), c.duration_minutes or '',
             c.member.full_name or c.member.email, c.member.email, c.zone]
            for c in CheckIn.objects.filter(check_in_time__range=(lo, hi)).select_related('member').order_by('check_in_time')]
    return ['Checked in', 'Checked out', 'Minutes', 'Member', 'Email', 'Zone'], rows


def machines(start, end):
    lo, hi = _bounds(start, end)
    in_range = Q(workout_entries__workout__started_at__range=(lo, hi))
    qs = (Exercise.objects.annotate(sets=Count('workout_entries__sets', filter=in_range, distinct=True),
                                    sessions=Count('workout_entries', filter=in_range, distinct=True),
                                    people=Count('workout_entries__workout__member', filter=in_range, distinct=True))
          .order_by('-sessions', 'name'))
    rows = [[e.name, e.get_category_display(), e.qr_tag_id, 'yes' if e.is_active else 'no', e.sessions, e.sets, e.people]
            for e in qs]
    return ['Machine', 'Category', 'QR code', 'In service', 'Times used', 'Sets logged', 'Members'], rows


def trainers(start, end):
    lo, hi = _bounds(start, end)
    rows = []
    for t in TrainerProfile.objects.select_related('user').order_by('user__first_name'):
        s = TrainerSession.objects.filter(trainer=t, scheduled_at__range=(lo, hi))
        enrol = Enrollment.objects.filter(course__trainer=t, enrolled_at__range=(lo, hi)).exclude(status='refunded')
        rows.append([t.user.full_name or t.user.email, t.title, s.filter(status='completed').count(),
                     s.filter(status='scheduled').count(), s.filter(status='cancelled').count(),
                     s.filter(status='no_show').count(),
                     _sar(s.exclude(status__in=['cancelled', 'pending_payment']).aggregate(x=Sum('amount_charged'))['x']),
                     enrol.count(), _sar(enrol.aggregate(x=Sum('amount_paid'))['x']),
                     f'{float(t.rating):.1f}' if t.total_reviews else ''])
    return ['Trainer', 'Title', '1:1 completed', '1:1 upcoming', '1:1 cancelled', 'No-shows', '1:1 sales (SAR)',
            'Course enrolments', 'Course sales (SAR)', 'Rating'], rows


REPORTS = {
    'revenue': ('Revenue', 'Every payment received in the period — memberships, shop, trainers, top-ups.', 'payments', revenue),
    'finance': ('Monthly finance summary', 'Money received per month by stream, with VAT.', 'account_balance', finance),
    'members': ('Member list', 'Every member with plan, status and expiry; marks who joined in the period.', 'group', members),
    'attendance': ('Attendance', 'Every gym check-in and check-out in the period.', 'event_available', attendance),
    'machines': ('Machine use', 'How often each machine was used and by how many members.', 'precision_manufacturing', machines),
    'trainers': ('Trainer performance', '1:1 sessions, course enrolments and sales per trainer.', 'school', trainers),
}
