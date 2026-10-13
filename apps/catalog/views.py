from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    TrainerProfile, TrainerAvailability,
    Course, CourseModule, Enrollment,
    TrainerSession, CourseReview, TrainerReview,
)
from .serializers import (
    TrainerProfileSerializer, TrainerAvailabilitySerializer,
    CourseListSerializer, CourseDetailSerializer, CourseModuleSerializer,
    EnrollmentSerializer, TrainerSessionSerializer,
    CourseReviewSerializer, TrainerReviewSerializer,
)


# ============================================
# TRAINERS
# ============================================
@api_view(['GET'])
@permission_classes([AllowAny])
def trainers_list(request):
    """
    GET /api/catalog/trainers/
    Query params: ?search=&verified=true&accepting=true
    """
    qs = TrainerProfile.objects.select_related('user').all()

    if request.query_params.get('verified') == 'true':
        qs = qs.filter(is_verified=True)
    if request.query_params.get('accepting') == 'true':
        qs = qs.filter(is_accepting_clients=True)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(user__first_name__icontains=search) | \
             qs.filter(user__last_name__icontains=search) | \
             qs.filter(title__icontains=search)

    return Response(TrainerProfileSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def trainer_detail(request, trainer_id):
    """
    GET /api/catalog/trainers/<id>/
    """
    trainer = get_object_or_404(TrainerProfile, id=trainer_id)
    data = TrainerProfileSerializer(trainer).data
    # Include their courses
    courses = trainer.courses.filter(status='published')
    data['courses'] = CourseListSerializer(courses, many=True).data
    return Response(data)


# ============================================
# COURSES
# ============================================
@api_view(['GET'])
@permission_classes([AllowAny])
def courses_list(request):
    """
    GET /api/catalog/courses/
    Query params: ?category=Hypertrophy&level=advanced&search=&featured=true
    """
    qs = Course.objects.filter(status='published').select_related('trainer__user')

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category__iexact=category)

    level = request.query_params.get('level')
    if level:
        qs = qs.filter(level=level)

    if request.query_params.get('featured') == 'true':
        qs = qs.filter(is_featured=True)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(title__icontains=search) | qs.filter(description__icontains=search)

    return Response(CourseListSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def course_detail(request, course_id):
    """
    GET /api/catalog/courses/<id>/
    """
    course = get_object_or_404(
        Course.objects.select_related('trainer__user'),
        id=course_id,
        status='published',
    )
    data = CourseDetailSerializer(course).data
    # Add reviews
    reviews = course.reviews.all()[:10]
    data['reviews'] = CourseReviewSerializer(reviews, many=True).data
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def course_categories(request):
    """
    GET /api/catalog/courses/categories/
    List all unique categories.
    """
    categories = Course.objects.filter(status='published') \
        .values_list('category', flat=True).distinct()
    return Response(list(categories))


# ============================================
# ENROLLMENTS
# ============================================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def my_enrollments(request):
    """
    GET  /api/catalog/enrollments/          → list my enrollments
    POST /api/catalog/enrollments/          → enroll in a course
    Body: { "course_id": 5 }
    """
    if request.method == 'GET':
        qs = Enrollment.objects.filter(member=request.user).select_related('course__trainer__user')
        return Response(EnrollmentSerializer(qs, many=True).data)

    # POST — enroll
    course_id = request.data.get('course_id')
    if not course_id:
        return Response({'detail': 'course_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    course = get_object_or_404(Course, id=course_id, status='published')

    if Enrollment.objects.filter(member=request.user, course=course).exists():
        return Response(
            {'detail': 'You are already enrolled in this course.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    enrollment = Enrollment.objects.create(
        member=request.user,
        course=course,
        amount_paid=course.price,
    )

    # Increment enrollment count
    course.total_enrolled += 1
    course.save(update_fields=['total_enrolled'])

    return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_module(request, enrollment_id, module_id):
    """
    POST /api/catalog/enrollments/<enrollment_id>/modules/<module_id>/complete/
    """
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, member=request.user)
    module = get_object_or_404(CourseModule, id=module_id, course=enrollment.course)

    enrollment.completed_modules.add(module)

    total = enrollment.course.modules.count()
    completed = enrollment.completed_modules.count()
    enrollment.progress_percent = int((completed / total) * 100) if total > 0 else 0

    if enrollment.progress_percent == 100:
        enrollment.status = 'completed'
        enrollment.completed_at = timezone.now()

    enrollment.save()

    return Response(EnrollmentSerializer(enrollment).data)


# ============================================
# 1:1 SESSIONS
# ============================================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def my_sessions(request):
    """
    GET  /api/catalog/sessions/         → my booked sessions
    POST /api/catalog/sessions/         → book a session
    Body: { "trainer_id": 3, "scheduled_at": "2025-11-14T09:30:00Z",
            "duration_minutes": 60, "focus_area": "Technique Analysis", "notes": "..." }
    """
    if request.method == 'GET':
        qs = TrainerSession.objects.filter(member=request.user).select_related('trainer__user')
        return Response(TrainerSessionSerializer(qs, many=True).data)

    serializer = TrainerSessionSerializer(data=request.data)
    if serializer.is_valid():
        trainer = get_object_or_404(
            TrainerProfile,
            id=request.data.get('trainer_id'),
        )
        session = serializer.save(
            member=request.user,
            trainer=trainer,
            amount_charged=trainer.hourly_rate,
        )
        return Response(TrainerSessionSerializer(session).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_session(request, session_id):
    """
    POST /api/catalog/sessions/<id>/cancel/
    """
    session = get_object_or_404(TrainerSession, id=session_id, member=request.user)
    if session.status != 'scheduled':
        return Response(
            {'detail': 'Only scheduled sessions can be cancelled.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    session.status = 'cancelled'
    session.save()
    return Response(TrainerSessionSerializer(session).data)


# ============================================
# REVIEWS
# ============================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def review_course(request, course_id):
    """
    POST /api/catalog/courses/<id>/review/
    Body: { "rating": 5, "comment": "Great course!" }
    """
    course = get_object_or_404(Course, id=course_id, status='published')

    if CourseReview.objects.filter(course=course, member=request.user).exists():
        return Response(
            {'detail': 'You already reviewed this course.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CourseReviewSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(course=course, member=request.user)

        # Recalculate course rating
        reviews = course.reviews.all()
        course.rating = round(sum(r.rating for r in reviews) / reviews.count(), 2)
        course.total_reviews = reviews.count()
        course.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def review_trainer(request, trainer_id):
    """
    POST /api/catalog/trainers/<id>/review/
    """
    trainer = get_object_or_404(TrainerProfile, id=trainer_id)

    if TrainerReview.objects.filter(trainer=trainer, member=request.user).exists():
        return Response(
            {'detail': 'You already reviewed this trainer.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = TrainerReviewSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(trainer=trainer, member=request.user)

        reviews = trainer.reviews.all()
        trainer.rating = round(sum(r.rating for r in reviews) / reviews.count(), 2)
        trainer.total_reviews = reviews.count()
        trainer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ============================================
# COURSE PLAYER
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_player(request, course_id):
    """
    GET /api/catalog/courses/<id>/player/
    Returns course details + member progress + current module.
    """
    course = get_object_or_404(
        Course.objects.select_related('trainer__user'),
        id=course_id,
        status='published',
    )

    # Check enrollment
    try:
        enrollment = Enrollment.objects.get(member=request.user, course=course)
    except Enrollment.DoesNotExist:
        return Response(
            {'detail': 'You are not enrolled in this course.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    completed_ids = set(enrollment.completed_modules.values_list('id', flat=True))
    modules = course.modules.all().order_by('order')

    module_data = []
    current_module = None
    for m in modules:
        is_completed = m.id in completed_ids
        is_current = False
        # Current = first uncompleted module
        if not is_completed and current_module is None:
            is_current = True
            current_module = m

        module_data.append({
            'id': m.id,
            'order': m.order,
            'title': m.title,
            'description': m.description,
            'week_number': m.week_number,
            'day_number': m.day_number,
            'video_url': m.video_url,
            'pdf_url': m.pdf_url,
            'duration_minutes': m.duration_minutes,
            'is_locked_until_prev': m.is_locked_until_prev,
            'is_completed': is_completed,
            'is_current': is_current,
        })

    return Response({
        'course': CourseListSerializer(course).data,
        'trainer': TrainerProfileSerializer(course.trainer).data,
        'enrollment': {
            'id': enrollment.id,
            'status': enrollment.status,
            'progress_percent': enrollment.progress_percent,
            'completed_count': len(completed_ids),
            'total_modules': modules.count(),
        },
        'modules': module_data,
        'current_module': {
            'id': current_module.id,
            'title': current_module.title,
            'order': current_module.order,
        } if current_module else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def next_workout_suggestion(request):
    """
    GET /api/catalog/next-workout/
    Returns a suggested workout template for today based on active enrollments.
    """
    # Find active enrollment
    enrollment = (
        Enrollment.objects
        .filter(member=request.user, status='active')
        .select_related('course')
        .first()
    )

    if not enrollment:
        return Response({
            'has_suggestion': False,
            'message': 'Enroll in a course to unlock guided workouts.',
        })

    course = enrollment.course
    # Return the current module details
    completed_ids = set(enrollment.completed_modules.values_list('id', flat=True))
    next_module = course.modules.exclude(id__in=completed_ids).order_by('order').first()

    if not next_module:
        return Response({
            'has_suggestion': False,
            'message': 'You have completed all modules in this course.',
        })

    return Response({
        'has_suggestion': True,
        'course_id': course.id,
        'course_title': course.title,
        'module': {
            'id': next_module.id,
            'title': next_module.title,
            'order': next_module.order,
            'description': next_module.description,
            'duration_minutes': next_module.duration_minutes,
        },
    })