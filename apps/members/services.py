"""
Approval + payment logic for MembershipRegistration.
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
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
    # password_hash is already a hash from set_password()
    user.password = reg.password_hash
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

    # 5. Optional welcome email (stub)
    _send_welcome_email(user, membership, reg)

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


def _send_welcome_email(user, membership, reg):
    """
    Stub — swap for real email backend later.
    Set EMAIL_BACKEND in settings to actually send.
    """
    subject = 'Welcome to Smart Gym — your pass is active'
    body = (
        f"Hi {user.first_name or user.email},\n\n"
        f"Your Smart Gym membership is now active.\n\n"
        f"  Pass ID:     {membership.pass_id}\n"
        f"  Iqama #:     {membership.iqama_number}\n"
        f"  Plan:        {membership.plan.display_name}\n"
        f"  Valid until: {membership.expiry_date}\n\n"
        f"Login: {settings.FRONTEND_URL}/login\n"
        f"Email: {user.email}\n\n"
        f"See you on the floor.\n— Smart Gym"
    )
    logger.info('WELCOME EMAIL → %s\n%s', user.email, body)
    # TODO: from django.core.mail import send_mail
    # send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])