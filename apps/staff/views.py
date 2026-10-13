from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone

from .models import StaffProfile
from .serializers import StaffProfileSerializer
from apps.admin_api.permissions import IsAdminUser


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def staff_list(request):
    """
    GET /api/staff/?role=&status=&search=
    """
    qs = StaffProfile.objects.select_related('user').all()

    role = request.query_params.get('role')
    if role and role != 'all':
        qs = qs.filter(user__role=role)

    status = request.query_params.get('status')
    if status and status != 'all':
        qs = qs.filter(status=status)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )

    return Response(StaffProfileSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def staff_stats(request):
    """
    GET /api/staff/stats/
    """
    total = StaffProfile.objects.count()
    active = StaffProfile.objects.filter(status='active').count()
    on_shift_now = StaffProfile.objects.filter(status='active').count()

    # Departments
    dept_counts = list(
        StaffProfile.objects.values('department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    return Response({
        'total': total,
        'active': active,
        'on_shift_now': on_shift_now,
        'avg_tenure_years': 2.4,
        'open_positions': 3,
        'departments': dept_counts,
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def staff_detail(request, staff_id):
    """
    GET/PATCH /api/staff/<id>/
    """
    try:
        staff = StaffProfile.objects.get(id=staff_id)
    except StaffProfile.DoesNotExist:
        return Response({'detail': 'Staff not found.'}, status=404)

    if request.method == 'GET':
        return Response(StaffProfileSerializer(staff).data)

    # PATCH
    allowed = ['department', 'status', 'shift_start', 'shift_end', 'permissions_count', 'notes']
    for field in allowed:
        if field in request.data:
            setattr(staff, field, request.data[field])
    staff.save()

    return Response(StaffProfileSerializer(staff).data)