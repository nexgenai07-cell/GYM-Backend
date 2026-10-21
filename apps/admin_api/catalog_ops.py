"""
Admin → Trainers & Courses: add and edit trainer profiles, verify them, take them off the
member portal, and run the course catalogue (draft → published → archived, lessons, covers).
Weekly booking hours and 1:1 pricing live on the Trainer hours page (ops.trainer_hours_*).
"""
import logging
import uuid
from decimal import Decimal, InvalidOperation

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.models import User
from apps.catalog.models import Course, CourseModule, Enrollment, TrainerProfile, TrainerSession
from apps.site_content.serializers import SiteImageUploadSerializer

from .permissions import IsAdminUser

logger = logging.getLogger(__name__)

LEVELS = dict(Course.LEVEL_CHOICES)
STATUSES = dict(Course.STATUS_CHOICES)


def _f(v):
    return round(float(v or 0), 2)


def _money(v, field, errors):
    try:
        d = Decimal(str(v)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        errors[field] = 'Enter an amount in SAR.'
        return None
    if d < 0 or d > Decimal('100000'):
        errors[field] = 'Enter an amount between 0 and 100,000.'
        return None
    return d


def _int(v, field, errors, lo, hi):
    try:
        n = int(v)
    except (TypeError, ValueError):
        errors[field] = f'Enter a whole number from {lo} to {hi}.'
        return None
    if not lo <= n <= hi:
        errors[field] = f'Enter a whole number from {lo} to {hi}.'
        return None
    return n


def _text(data, field, errors, max_len, required=False):
    v = str(data.get(field) or '').strip()
    if required and not v:
        errors[field] = 'Required.'
    elif len(v) > max_len:
        errors[field] = f'Keep it under {max_len} characters.'
    return v


def _save_image(request, folder):
    """Validates request.FILES['image'] and stores it; returns (url, error)."""
    ser = SiteImageUploadSerializer(data=request.data)
    if not ser.is_valid():
        return None, ' '.join(ser.errors.get('image', ['Invalid image.']))
    img = ser.validated_data.get('image')
    if img is None:
        return None, 'Choose an image to upload.'
    ext = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}[img.content_type]
    name = default_storage.save(f'{folder}/{uuid.uuid4().hex}.{ext}', img)
    url = default_storage.url(name)
    return (request.build_absolute_uri(url) if url.startswith('/') else url), None


# ============================================================
# TRAINERS
# ============================================================
def _trainer_row(t, counts=None):
    u = t.user
    c = (counts or {}).get(t.id, {})
    name = u.full_name or u.email
    return {
        'id': t.id, 'user_id': u.id, 'user_name': name, 'user_email': u.email, 'phone': u.phone or '',
        'first_name': u.first_name, 'last_name': u.last_name,
        'initials': ''.join(p[0] for p in name.split()[:2]).upper() or '?',
        'title': t.title, 'credentials': t.credentials, 'bio': t.bio, 'photo_url': t.photo_url,
        'specialties': t.specialties or [], 'years_experience': t.years_experience,
        'rating': _f(t.rating), 'total_reviews': t.total_reviews, 'total_students': t.total_students,
        'hourly_rate': _f(t.hourly_rate), 'is_verified': t.is_verified,
        'is_accepting_clients': t.is_accepting_clients, 'offers_1on1': t.offers_1on1,
        'is_active': u.is_active,   # false → hidden from the member portal
        'courses': c.get('courses', 0), 'upcoming_sessions': c.get('upcoming', 0),
    }


def _trainer_counts(ids):
    now = timezone.now()
    out = {i: {} for i in ids}
    for r in Course.objects.filter(trainer_id__in=ids).values('trainer_id').annotate(n=Count('id')):
        out[r['trainer_id']]['courses'] = r['n']
    for r in (TrainerSession.objects.filter(trainer_id__in=ids, scheduled_at__gte=now, status='scheduled')
              .values('trainer_id').annotate(n=Count('id'))):
        out[r['trainer_id']]['upcoming'] = r['n']
    return out


def _apply_trainer(t, u, data, errors):
    """Validates and copies editable fields onto the profile and user (not saved)."""
    if 'first_name' in data:
        u.first_name = _text(data, 'first_name', errors, 150, required=True)
    if 'last_name' in data:
        u.last_name = _text(data, 'last_name', errors, 150)
    if 'phone' in data:
        u.phone = _text(data, 'phone', errors, 20)
    if 'title' in data:
        t.title = _text(data, 'title', errors, 120, required=True)
    if 'credentials' in data:
        t.credentials = _text(data, 'credentials', errors, 200)
    if 'bio' in data:
        t.bio = _text(data, 'bio', errors, 4000)
    if 'specialties' in data:
        raw = data.get('specialties') or []
        if isinstance(raw, str):
            raw = raw.split(',')
        specs = [str(s).strip()[:40] for s in raw if str(s).strip()]
        if len(specs) > 12:
            errors['specialties'] = 'Up to 12 specialties.'
        t.specialties = specs[:12]
    if 'years_experience' in data:
        n = _int(data.get('years_experience'), 'years_experience', errors, 0, 60)
        if n is not None:
            t.years_experience = n
    if 'hourly_rate' in data:
        d = _money(data.get('hourly_rate'), 'hourly_rate', errors)
        if d is not None:
            t.hourly_rate = d
    for flag in ('is_verified', 'is_accepting_clients', 'offers_1on1'):
        if flag in data:
            setattr(t, flag, bool(data.get(flag)))
    if 'is_active' in data:
        u.is_active = bool(data.get('is_active'))


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def trainers(request):
    """
    GET  /api/admin/trainers/?search=&status=verified|unverified|hidden
    POST /api/admin/trainers/ {email, first_name, last_name, phone, title, ...}
         Adds a trainer. An existing member/staff account with that email is reused (its role
         becomes trainer unless it's admin/manager); otherwise an account without a password is
         created — trainers are shown to members, they don't log in.
    """
    if request.method == 'GET':
        qs = TrainerProfile.objects.select_related('user').order_by('-user__is_active', 'user__first_name')
        q = (request.query_params.get('search') or '').strip()
        if q:
            qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
                           | Q(user__email__icontains=q) | Q(title__icontains=q))
        st = request.query_params.get('status')
        if st == 'verified':
            qs = qs.filter(is_verified=True, user__is_active=True)
        elif st == 'unverified':
            qs = qs.filter(is_verified=False, user__is_active=True)
        elif st == 'hidden':
            qs = qs.filter(user__is_active=False)
        rows = list(qs)
        counts = _trainer_counts([t.id for t in rows])
        return Response([_trainer_row(t, counts) for t in rows])

    data = request.data
    errors = {}
    email = _text(data, 'email', errors, 254, required=True).lower()
    if email and '@' not in email:
        errors['email'] = 'Enter a valid email.'
    u = User.objects.filter(email__iexact=email).first() if email else None
    if u is not None and TrainerProfile.objects.filter(user=u).exists():
        errors['email'] = 'This person is already a trainer.'
    if u is None:
        u = User(email=email, username=email, role='trainer')
        u.set_unusable_password()
    t = TrainerProfile(user=u, hourly_rate=Decimal('0'))
    _apply_trainer(t, u, {'title': data.get('title', ''), 'first_name': data.get('first_name', ''), **data}, errors)
    if errors:
        return Response(errors, status=400)
    with transaction.atomic():
        if u.role not in ('admin', 'manager'):
            u.role = 'trainer'
        u.save()
        t.user = u
        t.save()
    logger.info('Trainer %s added by %s', u.email, request.user.email)
    return Response(_trainer_row(t, _trainer_counts([t.id])), status=201)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def trainer_update(request, trainer_id):
    """PATCH /api/admin/trainers/<id>/ — any editable field, incl. is_verified and is_active."""
    t = get_object_or_404(TrainerProfile.objects.select_related('user'), id=trainer_id)
    errors = {}
    _apply_trainer(t, t.user, request.data, errors)
    if errors:
        return Response(errors, status=400)
    if t.user_id == request.user.id and request.data.get('is_active') is False:
        return Response({'detail': 'You can’t hide your own account.'}, status=400)
    with transaction.atomic():
        t.user.save()
        t.save()
    return Response(_trainer_row(t, _trainer_counts([t.id])))


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([MultiPartParser, FormParser])
def trainer_photo(request, trainer_id):
    """POST /api/admin/trainers/<id>/photo/ multipart {image}."""
    t = get_object_or_404(TrainerProfile.objects.select_related('user'), id=trainer_id)
    url, err = _save_image(request, 'trainers')
    if err:
        return Response({'image': [err]}, status=400)
    t.photo_url = url
    t.save(update_fields=['photo_url', 'updated_at'])
    return Response(_trainer_row(t, _trainer_counts([t.id])))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def trainer_stats(request):
    """GET /api/admin/trainers/stats/"""
    active = TrainerProfile.objects.filter(user__is_active=True)
    return Response({
        'total': active.count(),
        'verified': active.filter(is_verified=True).count(),
        'accepting': active.filter(is_accepting_clients=True).count(),
        'hidden': TrainerProfile.objects.filter(user__is_active=False).count(),
        'avg_rating': _f(active.filter(total_reviews__gt=0).aggregate(a=Avg('rating'))['a']),
    })


# ============================================================
# COURSES
# ============================================================
def _course_row(c, modules=False):
    row = {
        'id': c.id, 'title': c.title, 'subtitle': c.subtitle, 'description': c.description,
        'category': c.category, 'level': c.level, 'level_label': LEVELS.get(c.level, c.level),
        'trainer_id': c.trainer_id, 'trainer_name': c.trainer.user.full_name or c.trainer.user.email,
        'cover_image_url': c.cover_image_url, 'promo_video_url': c.promo_video_url,
        'duration_weeks': c.duration_weeks, 'days_per_week': c.days_per_week,
        'estimated_minutes_per_session': c.estimated_minutes_per_session,
        'price': _f(c.price), 'is_included_with_pro': c.is_included_with_pro,
        'status': c.status, 'status_label': STATUSES.get(c.status, c.status), 'is_featured': c.is_featured,
        'rating': _f(c.rating), 'total_reviews': c.total_reviews,
        'total_enrolled': getattr(c, 'enrolled', None) if getattr(c, 'enrolled', None) is not None else c.total_enrolled,
        'module_count': getattr(c, 'module_count', None),
        'updated_at': c.updated_at,
    }
    if modules:
        row['modules'] = [{
            'id': m.id, 'order': m.order, 'title': m.title, 'description': m.description,
            'week_number': m.week_number, 'day_number': m.day_number, 'video_url': m.video_url,
            'pdf_url': m.pdf_url, 'duration_minutes': m.duration_minutes,
        } for m in c.modules.order_by('order')]
        row['module_count'] = len(row['modules'])
    return row


def _apply_course(c, data, errors):
    if 'title' in data:
        c.title = _text(data, 'title', errors, 200, required=True)
    if 'subtitle' in data:
        c.subtitle = _text(data, 'subtitle', errors, 200)
    if 'description' in data:
        c.description = _text(data, 'description', errors, 8000, required=True)
    if 'category' in data:
        c.category = _text(data, 'category', errors, 60, required=True)
    if 'level' in data:
        if data.get('level') not in LEVELS:
            errors['level'] = 'Choose a level.'
        else:
            c.level = data['level']
    if 'trainer_id' in data:
        t = TrainerProfile.objects.filter(id=data.get('trainer_id')).first()
        if t is None:
            errors['trainer_id'] = 'Choose a trainer.'
        else:
            c.trainer = t
    for field, lo, hi in (('duration_weeks', 1, 104), ('days_per_week', 1, 7), ('estimated_minutes_per_session', 5, 300)):
        if field in data:
            n = _int(data.get(field), field, errors, lo, hi)
            if n is not None:
                setattr(c, field, n)
    if 'price' in data:
        d = _money(data.get('price'), 'price', errors)
        if d is not None:
            c.price = d
    if 'promo_video_url' in data:
        v = _text(data, 'promo_video_url', errors, 200)
        if v and not v.startswith(('https://', 'http://')):
            errors['promo_video_url'] = 'Enter a full link (https://…).'
        c.promo_video_url = v
    for flag in ('is_included_with_pro', 'is_featured'):
        if flag in data:
            setattr(c, flag, bool(data.get(flag)))
    if 'status' in data:
        if data.get('status') not in STATUSES:
            errors['status'] = 'Choose a status.'
        else:
            c.status = data['status']


def _replace_modules(c, modules, errors):
    """Replaces the course's lessons. Lessons a member has completed keep their ids when sent back."""
    if not isinstance(modules, list) or len(modules) > 200:
        errors['modules'] = 'Send up to 200 lessons.'
        return
    existing = {m.id: m for m in c.modules.all()}
    keep, rows = set(), []
    for n, raw in enumerate(modules):
        e = {}
        m = existing.get(raw.get('id')) or CourseModule(course=c)
        m.order = n + 1
        m.title = _text(raw, 'title', e, 200, required=True)
        m.description = _text(raw, 'description', e, 4000)
        for field, lo, hi in (('week_number', 1, 104), ('day_number', 1, 7), ('duration_minutes', 1, 600)):
            v = _int(raw.get(field, 1), field, e, lo, hi)
            if v is not None:
                setattr(m, field, v)
        for field in ('video_url', 'pdf_url'):
            v = _text(raw, field, e, 200)
            if v and not v.startswith(('https://', 'http://')):
                e[field] = 'Enter a full link (https://…).'
            setattr(m, field, v)
        if e and 'modules' not in errors:
            field, msg = next(iter(e.items()))
            errors['modules'] = f"Lesson {n + 1} — {field.replace('_', ' ')}: {msg}"
        rows.append(m)
        if m.id:
            keep.add(m.id)
    if errors:
        return
    c.modules.exclude(id__in=keep).delete()
    for m in rows:
        m.save()


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
@parser_classes([JSONParser])
def courses(request):
    """
    GET  /api/admin/courses/?status=&q=&trainer=  — every course, drafts included.
    POST /api/admin/courses/ {title, description, category, trainer_id, …, modules?: [...]} → draft.
    """
    if request.method == 'GET':
        qs = (Course.objects.select_related('trainer__user')
              .annotate(enrolled=Count('enrollments', distinct=True), module_count=Count('modules', distinct=True))
              .order_by('-is_featured', '-updated_at'))
        st = request.query_params.get('status')
        if st in STATUSES:
            qs = qs.filter(status=st)
        if request.query_params.get('trainer'):
            qs = qs.filter(trainer_id=request.query_params['trainer'])
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(category__icontains=q) | Q(trainer__user__first_name__icontains=q))
        return Response([_course_row(c) for c in qs])

    c = Course(status='draft')
    errors = {}
    data = {'title': '', 'description': '', 'category': '', 'trainer_id': None, **request.data}
    _apply_course(c, data, errors)
    if errors:
        return Response(errors, status=400)
    with transaction.atomic():
        c.save()
        if 'modules' in request.data:
            _replace_modules(c, request.data['modules'], errors)
            if errors:
                transaction.set_rollback(True)
                return Response(errors, status=400)
    return Response(_course_row(c, modules=True), status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
@parser_classes([JSONParser])
def course_detail(request, course_id):
    """
    GET    /api/admin/courses/<id>/  — with lessons.
    PATCH  /api/admin/courses/<id>/  — any field; `modules` replaces the lesson list.
    DELETE /api/admin/courses/<id>/  — only when nobody is enrolled (archive it otherwise).
    """
    c = get_object_or_404(Course.objects.select_related('trainer__user'), id=course_id)
    if request.method == 'GET':
        return Response(_course_row(c, modules=True))
    if request.method == 'DELETE':
        if Enrollment.objects.filter(course=c).exists():
            return Response({'detail': 'Members are enrolled in this course — archive it instead.'}, status=400)
        c.delete()
        return Response(status=204)

    errors = {}
    _apply_course(c, request.data, errors)
    if not errors and c.status == 'published':
        if not c.description.strip():
            errors['description'] = 'Add a description before publishing.'
        lessons = request.data.get('modules') if 'modules' in request.data else None
        if (lessons is not None and not lessons) or (lessons is None and not c.modules.exists()):
            errors['modules'] = 'Add at least one lesson before publishing.'
    if errors:
        return Response(errors, status=400)
    with transaction.atomic():
        c.save()
        if 'modules' in request.data:
            _replace_modules(c, request.data['modules'], errors)
            if errors:
                transaction.set_rollback(True)
                return Response(errors, status=400)
    return Response(_course_row(c, modules=True))


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([MultiPartParser, FormParser])
def course_cover(request, course_id):
    """POST /api/admin/courses/<id>/cover/ multipart {image}."""
    c = get_object_or_404(Course.objects.select_related('trainer__user'), id=course_id)
    url, err = _save_image(request, 'courses')
    if err:
        return Response({'image': [err]}, status=400)
    c.cover_image_url = url
    c.save(update_fields=['cover_image_url', 'updated_at'])
    return Response(_course_row(c, modules=True))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def course_stats(request):
    """GET /api/admin/courses/stats/"""
    by = dict(Course.objects.values_list('status').annotate(n=Count('id')))
    paid = Enrollment.objects.exclude(status='refunded').aggregate(t=Sum('amount_paid'))['t']
    return Response({
        'total': sum(by.values()), 'published': by.get('published', 0), 'draft': by.get('draft', 0),
        'archived': by.get('archived', 0), 'featured': Course.objects.filter(is_featured=True, status='published').count(),
        'enrollments': Enrollment.objects.count(), 'course_revenue': _f(paid),
    })
