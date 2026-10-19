from datetime import date
from django.utils import timezone
from django.db.models import Q, Count
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from apps.members.models import (
    MembershipPlan, MembershipRegistration, Membership, CheckIn,
)
from apps.members.serializers import (
    MembershipPlanSerializer, MembershipSerializer, CheckInSerializer,
)
from apps.members.services import (
    approve_registration, reject_registration, bulk_approve_registrations,
)
from apps.catalog.models import Course, TrainerProfile
from apps.catalog.serializers import (
    CourseListSerializer, TrainerProfileSerializer,
)

from .serializers import (
    PublicPlanSerializer,
    RegistrationCreateSerializer,
    RegistrationStatusSerializer,
    AdminRegistrationSerializer,
    BulkApproveSerializer,
    RejectSerializer,
)
from .permissions import IsAdminOrManager

from django.conf import settings
print(">>> REGISTER VIEW LOADED, STORAGES keys =", list(settings.STORAGES.keys()))
# ============================================================
# PUBLIC — CATALOG
# ============================================================
@api_view(['GET'])
@permission_classes([AllowAny])
def public_plans(request):
    """GET /api/public/plans/"""
    qs = MembershipPlan.objects.filter(is_active=True)
    return Response(PublicPlanSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_courses(request):
    """GET /api/public/courses/?category=&featured=true"""
    qs = Course.objects.filter(status='published').select_related('trainer__user')
    if request.query_params.get('featured') == 'true':
        qs = qs.filter(is_featured=True)
    if (cat := request.query_params.get('category')):
        qs = qs.filter(category__iexact=cat)
    return Response(CourseListSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_trainers(request):
    """GET /api/public/trainers/?verified=true"""
    qs = TrainerProfile.objects.select_related('user').all()
    if request.query_params.get('verified') == 'true':
        qs = qs.filter(is_verified=True)
    return Response(TrainerProfileSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_facilities(request):
    """
    GET /api/public/facilities/
    Reads from apps.facilities if it exposes a Facility model;
    otherwise returns a static list.
    """
    try:
        from apps.facilities.models import Facility
        qs = Facility.objects.filter(is_active=True) if hasattr(Facility, 'is_active') \
             else Facility.objects.all()
        data = [
            {
                'id': f.id,
                'name': getattr(f, 'name', str(f)),
                'description': getattr(f, 'description', ''),
                'capacity': getattr(f, 'capacity', None),
                'image_url': getattr(getattr(f, 'image', None), 'url', None),
            } for f in qs
        ]
        return Response(data)
    except Exception:
        # Fallback static list — public site can render this immediately
        return Response([
            {'id': 1, 'name': 'Olympic Swimming Pool', 'description': '8-lane racing reservoir.', 'capacity': 40},
            {'id': 2, 'name': 'Pro Basketball Court', 'description': 'FIBA hardwood.', 'capacity': 20},
            {'id': 3, 'name': 'Combat & Boxing Pit', 'description': 'Octagon + force-sensor bags.', 'capacity': 30},
            {'id': 4, 'name': 'Steam & Cryo Recovery', 'description': 'Cryo chambers + sauna suites.', 'capacity': 15},
            {'id': 5, 'name': 'Volleyball Arena', 'description': 'League-grade flooring.', 'capacity': 24},
            {'id': 6, 'name': 'Heavy Iron Arena', 'description': '18 competition power racks.', 'capacity': 60},
        ])


@api_view(['GET'])
@permission_classes([AllowAny])
def public_articles(request):
    """GET /api/public/articles/  — reads from apps.cms if available."""
    try:
        from apps.cms.models import Article
        qs = Article.objects.filter(is_published=True)[:30] if hasattr(Article, 'is_published') \
             else Article.objects.all()[:30]
        data = [
            {
                'id': a.id,
                'title': getattr(a, 'title', ''),
                'slug': getattr(a, 'slug', ''),
                'excerpt': getattr(a, 'excerpt', ''),
                'cover_image_url': getattr(a, 'cover_image_url', '') or
                                   getattr(getattr(a, 'cover_image', None), 'url', ''),
                'published_at': getattr(a, 'published_at', None) or getattr(a, 'created_at', None),
                'author': getattr(getattr(a, 'author', None), 'full_name', ''),
            } for a in qs
        ]
        return Response(data)
    except Exception:
        return Response([])


# ============================================================
# PUBLIC — REGISTRATION
# ============================================================
@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def public_register(request):
    """
    POST /api/public/register/
    multipart/form-data with:
      iqama_number, full_name, email, phone, address, age, gender,
      photo (file), plan (id), duration_months, password
    """
    serializer = RegistrationCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    reg = serializer.save()

    # If MOCK_MADA=True, auto-mark payment as paid so you can test approval flow
    if getattr(settings, 'MOCK_MADA', False):
        reg.payment_status = 'paid'
        reg.payment_reference = f'MOCK-{reg.id:06d}'
        reg.payment_paid_at = timezone.now()
        reg.status = MembershipRegistration.STATUS_PAID
        reg.save(update_fields=['payment_status', 'payment_reference', 'payment_paid_at', 'status'])

    return Response(
        RegistrationStatusSerializer(reg).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def public_register_status(request, reg_id):
    """GET /api/public/register/<id>/status/"""
    reg = get_object_or_404(MembershipRegistration, id=reg_id)
    return Response(RegistrationStatusSerializer(reg).data)


@api_view(['POST'])
@permission_classes([AllowAny])
def public_payment_webhook(request, reg_id):
    """
    POST /api/public/register/<id>/payment/
    Payment gateway calls this after Mada charge succeeds/fails.
    Body: { "status": "paid" | "failed", "reference": "MADA-XXXX", "amount": 79.00 }
    """
    reg = get_object_or_404(MembershipRegistration, id=reg_id)
    payload_status = request.data.get('status', 'paid')
    reference = request.data.get('reference', '')
    amount = request.data.get('amount')

    if payload_status == 'paid':
        reg.payment_status = 'paid'
        reg.payment_reference = reference
        reg.payment_paid_at = timezone.now()
        if amount is not None:
            reg.payment_amount = amount
        if reg.status == MembershipRegistration.STATUS_PENDING:
            reg.status = MembershipRegistration.STATUS_PAID
        reg.save(update_fields=[
            'payment_status', 'payment_reference', 'payment_paid_at',
            'payment_amount', 'status',
        ])
        return Response({'ok': True, 'status': reg.status})

    reg.payment_status = 'failed'
    reg.payment_reference = reference
    reg.save(update_fields=['payment_status', 'payment_reference'])
    return Response({'ok': True, 'status': reg.payment_status})


# ============================================================
# ADMIN — REGISTRATIONS
# ============================================================
@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def admin_registrations(request):
    """
    GET /api/admin/registrations/?status=pending&search=&today=true
    """
    qs = MembershipRegistration.objects.select_related('plan', 'approved_by', 'created_user')

    st = request.query_params.get('status')
    if st and st != 'all':
        qs = qs.filter(status=st)

    if request.query_params.get('today') == 'true':
        qs = qs.filter(submitted_at__date=date.today())

    search = request.query_params.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(iqama_number__icontains=search) |
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    serializer = AdminRegistrationSerializer(qs, many=True, context={'request': request})
    return Response({
        'count': qs.count(),
        'results': serializer.data,
    })


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def admin_registration_detail(request, reg_id):
    """GET /api/admin/registrations/<id>/"""
    reg = get_object_or_404(
        MembershipRegistration.objects.select_related('plan', 'approved_by', 'created_user'),
        id=reg_id,
    )
    return Response(AdminRegistrationSerializer(reg, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAdminOrManager])
def admin_approve_registration(request, reg_id):
    """POST /api/admin/registrations/<id>/approve/"""
    reg = get_object_or_404(MembershipRegistration, id=reg_id)
    try:
        user = approve_registration(reg, approved_by=request.user)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    membership = Membership.objects.get(member=user)
    return Response({
        'ok': True,
        'registration': AdminRegistrationSerializer(reg, context={'request': request}).data,
        'user': {'id': user.id, 'email': user.email, 'full_name': user.full_name},
        'membership': MembershipSerializer(membership).data,
    })


@api_view(['POST'])
@permission_classes([IsAdminOrManager])
def admin_reject_registration(request, reg_id):
    """POST /api/admin/registrations/<id>/reject/  { reason }"""
    reg = get_object_or_404(MembershipRegistration, id=reg_id)
    ser = RejectSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    try:
        reject_registration(reg, reason=ser.validated_data['reason'], rejected_by=request.user)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'ok': True, 'status': reg.status})


@api_view(['POST'])
@permission_classes([IsAdminOrManager])
def admin_bulk_approve(request):
    """
    POST /api/admin/registrations/bulk-approve/
    Body: { "ids": [1,2,3] }              → approve only these
          { "only_today": true }          → approve all pending submitted today
          {}                              → approve ALL pending/paid
    """
    ser = BulkApproveSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    ids = ser.validated_data.get('ids')
    only_today = ser.validated_data.get('only_today', False)

    qs = MembershipRegistration.objects.filter(
        status__in=[
            MembershipRegistration.STATUS_PENDING,
            MembershipRegistration.STATUS_PAID,
        ]
    )
    if ids:
        qs = qs.filter(id__in=ids)
    if only_today:
        qs = qs.filter(submitted_at__date=date.today())

    approved, failed = bulk_approve_registrations(qs, approved_by=request.user)
    return Response({
        'ok': True,
        'approved_count': approved,
        'failed_count': len(failed),
        'failed': [{'id': rid, 'error': err} for rid, err in failed],
    })


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def admin_registration_stats(request):
    """GET /api/admin/registrations/stats/"""
    today = date.today()
    qs = MembershipRegistration.objects
    return Response({
        'pending': qs.filter(status=MembershipRegistration.STATUS_PENDING).count(),
        'paid': qs.filter(status=MembershipRegistration.STATUS_PAID).count(),
        'approved': qs.filter(status=MembershipRegistration.STATUS_APPROVED).count(),
        'rejected': qs.filter(status=MembershipRegistration.STATUS_REJECTED).count(),
        'today_total': qs.filter(submitted_at__date=today).count(),
        'today_pending': qs.filter(
            submitted_at__date=today,
            status__in=[
                MembershipRegistration.STATUS_PENDING,
                MembershipRegistration.STATUS_PAID,
            ],
        ).count(),
    })


# ============================================================
# ADMIN — MEMBER LOOKUP (gym entry)
# ============================================================
@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def admin_member_lookup(request):
    """
    GET /api/admin/members/lookup/?iqama=XXX
    Returns member + membership + registration photo + remaining days + today's session.
    """
    iqama = request.query_params.get('iqama', '').strip()
    if not iqama:
        return Response({'detail': 'iqama query param required.'}, status=400)

    try:
        membership = Membership.objects.select_related('member', 'plan').get(
            iqama_number__iexact=iqama,
        )
    except Membership.DoesNotExist:
        # Maybe they registered but aren't approved yet
        pending = MembershipRegistration.objects.filter(
            iqama_number__iexact=iqama,
        ).first()
        if pending:
            return Response({
                'found': False,
                'reason': 'registration_pending',
                'registration': AdminRegistrationSerializer(pending, context={'request': request}).data,
            }, status=status.HTTP_404_NOT_FOUND)
        return Response({'found': False, 'reason': 'not_found'}, status=404)

    member = membership.member

    # Registration photo (source)
    reg = getattr(member, 'source_registration', None)
    reg_photo_url = None
    if reg and reg.photo:
        reg_photo_url = request.build_absolute_uri(reg.photo.url)

    # Today's active session?
    today = timezone.localdate()
    active = CheckIn.objects.filter(
        member=member,
        check_in_time__date=today,
        check_out_time__isnull=True,
    ).first()

    return Response({
        'found': True,
        'member': {
            'id': member.id,
            'email': member.email,
            'full_name': member.full_name,
            'phone': member.phone,
            'avatar_url': request.build_absolute_uri(member.avatar.url) if member.avatar else None,
        },
        'membership': MembershipSerializer(membership).data,
        'registration_photo_url': reg_photo_url,
        'is_valid': (
            membership.status == 'active'
            and not membership.is_frozen
            and membership.days_remaining > 0
        ),
        'active_check_in': CheckInSerializer(active).data if active else None,
    })


@api_view(['POST'])
@permission_classes([IsAdminOrManager])
def admin_member_face_verify(request, member_id):
    """
    POST /api/admin/members/<id>/face-verify/
    Body: { "match": true|false, "confidence": 0.94 }  — stub.
    Logs the verification attempt. Real face matching is out of scope for now.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    member = get_object_or_404(User, id=member_id)

    matched = bool(request.data.get('match', False))
    confidence = float(request.data.get('confidence', 0.0))

    return Response({
        'ok': True,
        'member_id': member.id,
        'matched': matched,
        'confidence': confidence,
        'verified_by': request.user.email,
        'note': 'Face-verify stub — swap for real matcher (e.g. face_recognition / AWS Rekognition).',
    })


@api_view(['POST'])
@permission_classes([IsAdminOrManager])
def admin_check_in(request, member_id):
    """
    POST /api/admin/members/<id>/check-in/
    Body: { "facility": "...", "zone": "...", "face_verified": true }
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    member = get_object_or_404(User, id=member_id)

    # Prevent double check-in
    today = timezone.localdate()
    existing = CheckIn.objects.filter(
        member=member,
        check_in_time__date=today,
        check_out_time__isnull=True,
    ).first()
    if existing:
        return Response({
            'detail': 'Already checked in — check out first.',
            'check_in_id': existing.id,
        }, status=status.HTTP_400_BAD_REQUEST)

    ci = CheckIn.objects.create(
        member=member,
        facility=request.data.get('facility', 'Metro Station Core 01'),
        zone=request.data.get('zone', ''),
        verified_by=request.user,
        face_verified=bool(request.data.get('face_verified', False)),
    )

    # Increment membership counter
    try:
        m = member.membership
        m.total_check_ins = (m.total_check_ins or 0) + 1
        m.save(update_fields=['total_check_ins'])
    except Exception:
        pass

    return Response(CheckInSerializer(ci).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminOrManager])
def admin_check_out(request, check_in_id):
    """
    POST /api/admin/check-ins/<check_in_id>/check-out/
    """
    ci = get_object_or_404(CheckIn, id=check_in_id)
    if ci.check_out_time:
        return Response({'detail': 'Already checked out.'}, status=400)

    ci.check_out_time = timezone.now()
    ci.duration_minutes = int((ci.check_out_time - ci.check_in_time).total_seconds() / 60)
    ci.save()
    return Response(CheckInSerializer(ci).data)