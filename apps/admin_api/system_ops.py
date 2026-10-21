"""
Admin → Settings: what this deployment is actually configured to do. Read-only — these values
come from the server's environment variables. Never returns secrets, only whether they're set.
"""
from django.conf import settings
from django.db import connection
from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsAdminUser

ACCESS = [   # mirrors the checks in the code (IsAdminUser, staff_ops._guard, members_ops role rules)
    {'role': 'Admin', 'portal': True, 'can': [
        'Everything in this admin portal',
        'Add, edit and suspend admins and managers',
        'Change member and staff roles',
    ]},
    {'role': 'Manager', 'portal': True, 'can': [
        'Everything in this admin portal',
        'Add and edit trainers, nutritionists and receptionists',
    ], 'cannot': ['Change admins or managers', 'Change roles']},
    {'role': 'Trainer · Nutritionist · Receptionist', 'portal': False, 'can': [
        'Listed on the staff roster for scheduling',
    ], 'cannot': ['Sign in to this admin portal']},
    {'role': 'Member', 'portal': False, 'can': ['The member portal: pass, payments, classes, courses, shop']},
]


def _moyasar_mode():
    key = settings.MOYASAR_SECRET_KEY or ''
    if key.startswith('sk_live_'):
        return 'live'
    if key.startswith('sk_test_'):
        return 'test'
    return 'not set' if not key else 'unknown key'


def _capacity():
    if settings.GYM_CAPACITY:
        return {'value': settings.GYM_CAPACITY, 'source': 'GYM_CAPACITY'}
    from apps.members.models import FacilityAddon
    total = FacilityAddon.objects.filter(item__is_active=True).aggregate(t=Sum('capacity'))['t'] or 0
    return {'value': total, 'source': 'sum of facility capacities (Facilities page)'}


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_status(request):
    """GET /api/admin/settings/"""
    email_backend = settings.EMAIL_BACKEND.rsplit('.', 2)[-2]
    smtp = email_backend == 'smtp'
    return Response({
        'payments': {
            'provider': 'Moyasar',
            'mode': _moyasar_mode(),
            'publishable_key_set': bool(settings.MOYASAR_PUBLISHABLE_KEY),
            'webhook_secret_set': bool(settings.MOYASAR_WEBHOOK_SECRET),
            'currency': 'SAR',
            'vat_rate_percent': round(float(settings.SHOP_VAT_RATE) * 100, 2),
        },
        'email': {
            'sending': smtp,
            'method': f'SMTP ({settings.EMAIL_HOST})' if smtp else 'Not sending — emails are only written to the server log',
            'from': settings.DEFAULT_FROM_EMAIL,
            'contact_form_notifies': settings.CONTACT_NOTIFY_EMAIL or None,
        },
        'storage': {
            'uploads': (f'Cloudinary (folder “{settings.CLOUDINARY_FOLDER}”)' if settings.USE_CLOUDINARY
                        else 'Server disk — uploads are lost on redeploy'),
            'durable': settings.USE_CLOUDINARY,
        },
        'gym': {
            'time_zone': settings.TIME_ZONE,
            'capacity': _capacity(),
            'portal_url': [u.strip() for u in settings.FRONTEND_URL.split(',') if u.strip()],
        },
        'server': {
            'database': {'postgresql': 'PostgreSQL', 'sqlite': 'SQLite'}.get(connection.vendor, connection.vendor),
            'debug': settings.DEBUG,
        },
        'access': ACCESS,
        'me': {'email': request.user.email, 'name': request.user.full_name, 'role': request.user.role},
    })
