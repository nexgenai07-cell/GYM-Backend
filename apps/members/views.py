from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils import timezone

from .models import MembershipPlan, Membership, CheckIn
from .serializers import (
    MembershipPlanSerializer,
    MembershipSerializer,
    CheckInSerializer,
)


# ============================================
# MEMBERSHIP PLANS (public)
# ============================================
@api_view(['GET'])
@permission_classes([AllowAny])
def plans_list(request):
    """
    GET /api/members/plans/
    Returns all active membership plans.
    """
    plans = MembershipPlan.objects.filter(is_active=True)
    return Response(MembershipPlanSerializer(plans, many=True).data)


# ============================================
# MY MEMBERSHIP
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_membership(request):
    """
    GET /api/members/membership/
    Returns the current user's membership.
    """
    try:
        membership = Membership.objects.get(member=request.user)
        return Response(MembershipSerializer(membership).data)
    except Membership.DoesNotExist:
        return Response(
            {'detail': 'You have no active membership.'},
            status=status.HTTP_404_NOT_FOUND,
        )


# ============================================
# CHECK-INS
# ============================================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def check_ins(request):
    """
    GET  /api/members/check-ins/  → list of user's check-ins
    POST /api/members/check-ins/  → create a new check-in
    """
    if request.method == 'GET':
        entries = CheckIn.objects.filter(member=request.user)[:50]
        return Response(CheckInSerializer(entries, many=True).data)

    # POST — new check-in
    serializer = CheckInSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(member=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_out(request, check_in_id):
    """
    POST /api/members/check-ins/<id>/check-out/
    Closes an active check-in and calculates duration.
    """
    try:
        entry = CheckIn.objects.get(id=check_in_id, member=request.user)
    except CheckIn.DoesNotExist:
        return Response(
            {'detail': 'Check-in not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if entry.check_out_time:
        return Response(
            {'detail': 'Already checked out.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    entry.check_out_time = timezone.now()
    duration = (entry.check_out_time - entry.check_in_time).total_seconds() / 60
    entry.duration_minutes = int(duration)
    entry.save()

    return Response(CheckInSerializer(entry).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_member(request, member_id):
    """
    GET /api/members/verify/<member_id>/
    Public — used as the QR payload target for facility staff scanning.
    Returns basic verification info (name, tier, status, expiry).
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        u = User.objects.get(id=member_id)
    except User.DoesNotExist:
        return Response(
            {'valid': False, 'reason': 'Member not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        membership = Membership.objects.select_related('plan').get(member=u)
    except Membership.DoesNotExist:
        return Response({
            'valid': False,
            'member_id': u.id,
            'name': getattr(u, 'full_name', None) or u.email,
            'reason': 'No active membership.',
        })

    is_active = (
        membership.status == 'active'
        and not membership.is_frozen
        and membership.days_remaining > 0
    )

    return Response({
        'valid': is_active,
        'member_id': u.id,
        'name': (
            getattr(u, 'full_name', None)
            or f"{u.first_name} {u.last_name}".strip()
            or u.email
        ),
        'email': u.email,
        'tier': membership.plan.display_name,
        'status': membership.status,
        'expiry_date': str(membership.expiry_date),
        'days_remaining': membership.days_remaining,
        'pass_id': membership.pass_id,
    })