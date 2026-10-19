"""
Approval + payment logic for MembershipRegistration.
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.conf import settings
import logging

from .models import MembershipRegistration, Membership

User = get_user_model()
logger = logging.getLogger(__name__)


# ============================================================
# PLAN → EXPIRY DATE
# ============================================================
def compute_expiry(start: date, months: int) -> date:
    """
    Add N calendar months to start date. Handles month-length edge cases
    (e.g. Jan 31 + 1 month = Feb 28/29).
    """
    return start + relativedelta(months=months)


# ============================================================
# APPROVE ONE REGISTRATION
# ============================================================
@transaction.atomic
def approve_registration(reg: MembershipRegistration, approved_by=None):
    """
    Approve a single registration:
      1. Create a User account (role='member')
      2. Create a Membership (dates computed from plan duration)
      3. Link both back to the registration
      4. Mark status='approved'
    Returns the created User.

    Raises ValueError if the registration can't be approved.
    """
    if reg.status == MembershipRegistration.STATUS_APPROVED:
        raise ValueError('Registration is already approved.')

    if reg.status == MembershipRegistration.STATUS_REJECTED:
        raise ValueError('Registration was rejected — cannot approve.')

    if reg.created_user_id:
        raise ValueError('A user has already been created for this registration.')

    if reg.payment_status != 'paid':
        raise ValueError('Registration has not been paid — cannot approve.')

    # Live re-check with Moyasar — payment_status alone isn't proof (refunds, manual edits).
    from apps.public_api.moyasar import confirm_paid_for_approval, MoyasarError
    try:
        confirm_paid_for_approval(reg)
    except MoyasarError as exc:
        raise ValueError(str(exc)) from exc

    # 1. Guard against email / iqama collisions (defensive — unique fields should prevent)
    if User.objects.filter(email=reg.email).exists():
        raise ValueError(f'A user with email {reg.email} already exists.')

    # 2. Create the User
    user = User(
        email=reg.email,
        username=reg.email,          # username is required on AbstractUser
        first_name=_split_name(reg.full_name)[0],
        last_name=_split_name(reg.full_name)[1],
        phone=reg.phone,
        role='member',
        is_verified=True,            # admin approved = verified
        is_active=True,
    )
    # Fresh temporary password (replaces the one chosen at signup); emailed below,
    # never logged. Stored hashed by set_password().
    temp_password = generate_temp_password()
    user.set_password(temp_password)
    user.must_change_password = True   # API is locked to "change password" until they do
    user.save()

    # 3. Create the Membership
    start = date.today()
    expiry = compute_expiry(start, reg.duration_months)

    membership = Membership.objects.create(
        member=user,
        plan=reg.plan,
        status='active',
        start_date=start,
        expiry_date=expiry,
        iqama_number=reg.iqama_number,
        lifetime_value=reg.payment_amount or reg.total_price,
    )

    # 4. Link back
    reg.created_user = user
    reg.status = MembershipRegistration.STATUS_APPROVED
    reg.approved_at = timezone.now()
    if approved_by is not None:
        reg.approved_by = approved_by
    reg.save(update_fields=[
        'created_user', 'status', 'approved_at', 'approved_by',
    ])

    logger.info(
        'Approved registration #%s → user %s, membership %s, expires %s',
        reg.id, user.email, membership.pass_id, expiry,
    )

    # 5. Welcome email with the login details — only once the approval is committed,
    #    so a rolled-back approval never emails a password that doesn't work.
    transaction.on_commit(lambda: _send_welcome_email(user, membership, temp_password))

    return user


# ============================================================
# REJECT ONE
# ============================================================
def reject_registration(reg: MembershipRegistration, reason: str = '', rejected_by=None):
    if reg.status == MembershipRegistration.STATUS_APPROVED:
        raise ValueError('Cannot reject an already-approved registration.')

    reg.status = MembershipRegistration.STATUS_REJECTED
    reg.rejection_reason = reason or 'No reason provided.'
    reg.save(update_fields=['status', 'rejection_reason'])
    logger.info('Rejected registration #%s: %s', reg.id, reason)


# ============================================================
# BULK APPROVE
# ============================================================
def bulk_approve_registrations(queryset, approved_by=None):
    """
    Approve every registration in queryset.
    Returns (approved_count, failed_list) where failed_list is [(reg_id, error_str)].
    """
    approved_count = 0
    failed = []

    for reg in queryset:
        try:
            approve_registration(reg, approved_by=approved_by)
            approved_count += 1
        except Exception as exc:
            logger.exception('Bulk approve failed for reg #%s', reg.id)
            failed.append((reg.id, str(exc)))

    return approved_count, failed


# ============================================================
# HELPERS
# ============================================================
def _split_name(full_name: str):
    parts = (full_name or '').strip().split(maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0] if parts else '', ''


# No look-alike characters (0/O, 1/l/I) so it can be typed from an email.
TEMP_PASSWORD_CHARS = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
TEMP_PASSWORD_LENGTH = 12
DEFAULT_MEMBER_PORTAL = 'https://gym-member-and-admin.vercel.app'
CONSOLE_EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


def generate_temp_password():
    """12 chars from a 54-symbol alphabet (~69 bits), via the secrets module.
    (BaseUserManager.make_random_password() was removed in Django 5.1.)"""
    return get_random_string(TEMP_PASSWORD_LENGTH, TEMP_PASSWORD_CHARS)


def member_portal_url():
    """
    One URL for emails. FRONTEND_URL is a comma-separated origin list in
    production ("http://localhost:5173,https://gym-member-and-admin.vercel.app"),
    so prefer its first https entry; locally that is the localhost one.
    """
    urls = [u.strip().rstrip('/') for u in settings.FRONTEND_URL.split(',') if u.strip()]
    https = [u for u in urls if u.startswith('https://')]
    return (https or urls or [DEFAULT_MEMBER_PORTAL])[0]


def _send_welcome_email(user, membership, temp_password):
    """
    Emails the login details. The body contains a password, so it is never
    logged, and in production it is not handed to the console backend
    (which would print it into the server logs).
    """
    if settings.EMAIL_BACKEND == CONSOLE_EMAIL_BACKEND and not settings.DEBUG:
        logger.error(
            'Welcome email for %s NOT sent: EMAIL_BACKEND is the console backend, which would '
            'print the temporary password into the logs. Configure SMTP, then reset this '
            "member's password from the admin.", user.email,
        )
        return

    subject = 'Welcome to Smart Gym — your membership is active'
    body = (
        f"Hi {user.first_name or user.email},\n\n"
        f"Your Smart Gym membership is now active.\n\n"
        f"  Pass ID:     {membership.pass_id}\n"
        f"  Iqama #:     {membership.iqama_number}\n"
        f"  Plan:        {membership.plan.display_name}\n"
        f"  Valid until: {membership.expiry_date}\n\n"
        f"YOUR LOGIN\n"
        f"  Login page:         {member_portal_url()}/login\n"
        f"  Email:              {user.email}\n"
        f"  Temporary password: {temp_password}\n\n"
        f"IMPORTANT: this is a temporary password. Change it as soon as you log in.\n"
        f"Never share it — Smart Gym staff will never ask for it.\n"
        f"The password you chose when you registered is no longer used.\n\n"
        f"See you on the floor.\n— Smart Gym"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception:
        # Approval is already committed; don't fail it — but make it visible (without the body).
        logger.exception('Welcome email to %s failed to send.', user.email)
        return
    logger.info('Welcome email sent to %s (membership %s).', user.email, membership.pass_id)