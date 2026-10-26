"""
Admin → Staff: the team roster. Everyone with a staff role, their department, shift hours and
status. Admins and managers sign in to this portal (they get an emailed invite with a temporary
password); other roles are listed for scheduling only.

Rules: only admins can add, edit or promote admins/managers; nobody can suspend or demote
themselves.
"""
import logging
from datetime import date, time

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import User
from apps.staff.models import StaffProfile

from .permissions import IsAdminUser

logger = logging.getLogger(__name__)

STAFF_ROLES = ['admin', 'manager', 'trainer', 'nutritionist', 'receptionist']
PORTAL_ROLES = {'admin', 'manager'}
ROLE_LABELS = dict(User.ROLE_CHOICES)
DEPARTMENTS = dict(StaffProfile.DEPARTMENT_CHOICES)
STATUSES = dict(StaffProfile.STATUS_CHOICES)
DEFAULT_DEPT = {'admin': 'executive', 'manager': 'operations', 'trainer': 'coaching',
                'nutritionist': 'clinical', 'receptionist': 'front_desk'}


def _parse_time(v):
    if v in (None, ''):
        return None
    try:
        h, m = str(v).split(':')[:2]
        return time(int(h), int(m))
    except (ValueError, TypeError):
        return 'bad'


def _on_shift(p, now_t):
    """Active with shift hours that cover now (overnight shifts wrap past midnight)."""
    if p is None or p.status != 'active' or not (p.shift_start and p.shift_end):
        return False
    if p.shift_start <= p.shift_end:
        return p.shift_start <= now_t < p.shift_end
    return now_t >= p.shift_start or now_t < p.shift_end


def _row(u, now_t=None):
    p = getattr(u, 'staff_profile', None)
    now_t = now_t or timezone.localtime().time()
    name = u.full_name or u.email
    joined = (p.joined_at if p and p.joined_at else timezone.localtime(u.date_joined).date())
    status = 'suspended' if not u.is_active else (p.status if p else 'active')
    return {
        'id': u.id, 'user_name': name, 'first_name': u.first_name, 'last_name': u.last_name,
        'user_email': u.email, 'phone': u.phone or '',
        'initials': ''.join(x[0] for x in name.split()[:2]).upper() or '?',
        'role': u.role, 'role_label': ROLE_LABELS.get(u.role, u.role),
        'department': DEFAULT_DEPT.get(u.role, 'operations'),        # set by the role, not editable
        'department_label': DEPARTMENTS.get(DEFAULT_DEPT.get(u.role, 'operations')),
        'status': status, 'status_label': STATUSES.get(status, status),
        'shift_start': p.shift_start.strftime('%H:%M') if p and p.shift_start else '',
        'shift_end': p.shift_end.strftime('%H:%M') if p and p.shift_end else '',
        'shift_display': (p.shift_display if p and p.shift_start and p.shift_end else 'Hours not set'),
        'on_shift': _on_shift(p, now_t) and u.is_active,
        'joined_at': joined, 'notes': p.notes if p else '',
        'can_sign_in': u.role in PORTAL_ROLES and u.is_active and u.has_usable_password(),
        'last_login': u.last_login,
        'has_trainer_profile': hasattr(u, 'trainer_profile'),
    }


def _invite(u, staff, reset=False):
    """Emails a temporary password and the admin sign-in link. Returns an error message or None."""
    from apps.members.services import CONSOLE_EMAIL_BACKEND, generate_temp_password, member_portal_url
    if settings.EMAIL_BACKEND == CONSOLE_EMAIL_BACKEND and not settings.DEBUG:
        return 'Email isn’t configured (SMTP), so the sign-in details can’t be sent.'
    temp = generate_temp_password()
    u.set_password(temp)
    u.must_change_password = True
    u.save(update_fields=['password', 'must_change_password'])
    intro = ('Your Smart Gym admin password was reset.' if reset
             else f'You’ve been added to the Smart Gym team as {ROLE_LABELS.get(u.role, u.role)}.')
    try:
        intro_ar = ('أُعيد تعيين كلمة مرور حسابك الإداري في سمارت جيم.' if reset
                    else 'تمت إضافتك إلى فريق سمارت جيم.')
        send_mail('Smart Gym — your admin sign-in · بيانات الدخول الإدارية',
                  f"Hi {u.first_name or u.email},\n\n{intro}\n\n"
                  f"  Sign in at:         {member_portal_url()}/admin/login\n  Email:              {u.email}\n"
                  f"  Temporary password: {temp}\n\nYou'll choose your own password when you first sign in.\n— Smart Gym\n\n"
                  f"────────────\n\nمرحبًا {u.first_name or u.email}،\n\n{intro_ar}\n\n"
                  f"  صفحة الدخول: {member_portal_url()}/admin/login\n  البريد الإلكتروني: {u.email}\n"
                  f"  كلمة المرور المؤقتة: {temp}\n\nستختار كلمة مرورك عند أول تسجيل دخول.\n— سمارت جيم",
                  settings.DEFAULT_FROM_EMAIL, [u.email])
    except Exception:   # noqa: BLE001
        logger.exception('Staff invite email to %s failed.', u.email)
        return 'The account is ready but the email failed to send — use “Send sign-in email” to retry.'
    logger.info('Sign-in details for %s sent by %s', u.email, staff.email)
    return None


def _validate(data, errors, creating):
    out = {}
    for f, n, required in (('first_name', 150, True), ('last_name', 150, False), ('phone', 20, False)):
        if f in data or creating:
            v = str(data.get(f) or '').strip()
            if required and not v:
                errors[f] = 'Required.'
            elif len(v) > n:
                errors[f] = f'Keep it under {n} characters.'
            out[f] = v
    if 'role' in data or creating:
        if data.get('role') not in STAFF_ROLES:
            errors['role'] = 'Choose a role.'
        out['role'] = data.get('role')
    if 'status' in data:
        if data.get('status') not in STATUSES:
            errors['status'] = 'Choose a status.'
        out['status'] = data.get('status')
    for f in ('shift_start', 'shift_end'):
        if f in data:
            t = _parse_time(data.get(f))
            if t == 'bad':
                errors[f] = 'Use HH:MM.'
            out[f] = t
    if 'shift_start' in out or 'shift_end' in out:
        start, end = out.get('shift_start', 'missing'), out.get('shift_end', 'missing')
        if 'missing' in (start, end) or (start is None) != (end is None):
            errors.setdefault('shift_end', 'Set both start and end, or clear both.')
        elif start is not None and start == end:
            errors.setdefault('shift_end', 'End must differ from start.')
    if 'joined_at' in data:
        v = data.get('joined_at')
        try:
            out['joined_at'] = date.fromisoformat(v) if v else None
        except (TypeError, ValueError):
            errors['joined_at'] = 'Use a date.'
        if out.get('joined_at') and out['joined_at'] > timezone.localdate():
            errors['joined_at'] = 'Can’t be in the future.'
    if 'notes' in data:
        out['notes'] = str(data.get('notes') or '')[:2000]
    return out


def _guard(request, target_role_before, target_role_after):
    """Managers can't touch admins/managers or hand out those roles."""
    if request.user.role == 'admin':
        return None
    if target_role_before in PORTAL_ROLES or target_role_after in PORTAL_ROLES:
        return 'Only an admin can add or change admins and managers.'
    return None


def _save(u, fields):
    for f in ('first_name', 'last_name', 'phone', 'role'):
        if f in fields:
            setattr(u, f, fields[f])
    if 'status' in fields:
        u.is_active = fields['status'] != 'suspended'
    u.save()
    p, _ = StaffProfile.objects.get_or_create(user=u, defaults={'department': DEFAULT_DEPT.get(u.role, 'operations')})
    p.department = DEFAULT_DEPT.get(u.role, 'operations')   # the role decides the department
    for f in ('shift_start', 'shift_end', 'joined_at', 'notes'):
        if f in fields:
            setattr(p, f, fields[f])
    if 'status' in fields:
        p.status = fields['status']
    p.save()


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def staff(request):
    """
    GET  /api/admin/staff/?role=&search=&status=
    POST /api/admin/staff/ {email, first_name, last_name, phone, role, shift_start, shift_end, joined_at}
         Admins/managers get an email invite to sign in; an existing account with that email is promoted.
    """
    if request.method == 'GET':
        qs = User.objects.filter(role__in=STAFF_ROLES).select_related('staff_profile').order_by('-is_active', 'first_name')
        role = request.query_params.get('role')
        if role in STAFF_ROLES:
            qs = qs.filter(role=role)
        q = (request.query_params.get('search') or '').strip()
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
        now_t = timezone.localtime().time()
        rows = [_row(u, now_t) for u in qs]
        st = request.query_params.get('status')
        if st == 'on_shift':
            rows = [r for r in rows if r['on_shift']]
        elif st in STATUSES:
            rows = [r for r in rows if r['status'] == st]
        return Response(rows)

    errors = {}
    email = str(request.data.get('email') or '').strip().lower()
    if '@' not in email:
        errors['email'] = 'Enter a valid email.'
    fields = _validate(request.data, errors, creating=True)
    u = User.objects.filter(email__iexact=email).first() if email else None
    if u is not None and u.role in STAFF_ROLES:
        errors['email'] = 'This person is already on the team.'
    if errors:
        return Response(errors, status=400)
    msg = _guard(request, u.role if u else None, fields['role'])
    if msg:
        return Response({'detail': msg}, status=403)
    with transaction.atomic():
        if u is None:
            u = User(email=email, username=email)
            u.set_unusable_password()
        _save(u, fields)
    warning = _invite(u, request.user) if u.role in PORTAL_ROLES else None
    logger.info('Staff %s (%s) added by %s', u.email, u.role, request.user.email)
    return Response({**_row(u), 'warning': warning}, status=201)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def staff_update(request, user_id):
    """PATCH /api/admin/staff/<user_id>/ — name, phone, role, status, shift, joined_at, notes (department follows the role)."""
    u = get_object_or_404(User.objects.select_related('staff_profile'), id=user_id, role__in=STAFF_ROLES)
    errors = {}
    fields = _validate(request.data, errors, creating=False)
    if errors:
        return Response(errors, status=400)
    msg = _guard(request, u.role, fields.get('role', u.role))
    if msg:
        return Response({'detail': msg}, status=403)
    if u.id == request.user.id and (fields.get('status') == 'suspended' or fields.get('role', u.role) != u.role):
        return Response({'detail': 'You can’t suspend yourself or change your own role.'}, status=400)
    if (u.role == 'admin' and (fields.get('role', 'admin') != 'admin' or fields.get('status') == 'suspended')
            and not User.objects.filter(role='admin', is_active=True).exclude(id=u.id).exists()):
        return Response({'detail': 'Keep at least one active admin.'}, status=400)
    was_portal = u.role in PORTAL_ROLES and u.has_usable_password()
    with transaction.atomic():
        _save(u, fields)
    warning = None
    if u.role in PORTAL_ROLES and not was_portal and u.is_active:
        warning = _invite(u, request.user)          # promoted: send sign-in details
    return Response({**_row(u), 'warning': warning})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def staff_send_signin(request, user_id):
    """POST /api/admin/staff/<user_id>/send-sign-in/ — new temporary password by email (admins/managers)."""
    u = get_object_or_404(User, id=user_id, role__in=PORTAL_ROLES)
    msg = _guard(request, u.role, u.role)
    if msg and u.id != request.user.id:
        return Response({'detail': msg}, status=403)
    if not u.is_active:
        return Response({'detail': 'Reinstate this account first.'}, status=400)
    err = _invite(u, request.user, reset=u.has_usable_password())
    if err:
        return Response({'detail': err}, status=502 if 'failed' in err else 400)
    return Response({'detail': f'Sign-in details emailed to {u.email}.'})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def staff_stats(request):
    """GET /api/admin/staff/stats/ — all from the roster; tenure from the start date (or account date)."""
    users = list(User.objects.filter(role__in=STAFF_ROLES).select_related('staff_profile'))
    now_t, today = timezone.localtime().time(), timezone.localdate()
    rows = [_row(u, now_t) for u in users]
    active = [r for r in rows if r['status'] != 'suspended']
    tenure = [(today - r['joined_at']).days / 365.25 for r in active]
    return Response({
        'total': len(active),
        'on_shift_now': sum(r['on_shift'] for r in rows),
        'on_leave': sum(r['status'] == 'on_leave' for r in rows),
        'suspended': sum(r['status'] == 'suspended' for r in rows),
        'hours_not_set': sum(r['shift_display'] == 'Hours not set' for r in active),
        'avg_tenure_years': round(sum(tenure) / len(tenure), 1) if tenure else 0,
        'by_role': {k: sum(r['role'] == k for r in active) for k in STAFF_ROLES},
    })
