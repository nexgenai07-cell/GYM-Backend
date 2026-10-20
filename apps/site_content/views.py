import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, F, Max, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes, throttle_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from apps.admin_api.permissions import IsAdminUser

from .models import PAGES, ContactMessage, SiteImage, SiteText
from .serializers import (
    ContactCreateSerializer, ContactMessageSerializer, SiteImageSerializer,
    SiteImageUploadSerializer, SiteTextSerializer,
)

logger = logging.getLogger(__name__)
CONSOLE_EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# ============================================================
# PUBLIC
# ============================================================
@api_view(['GET'])
@permission_classes([AllowAny])
def public_site_content(request):
    """
    GET /api/public/site-content/
    Every text (en + ar) and image URL of the public site, keyed like the
    site's i18n keys. The site uses these over its built-in text.
    """
    texts = {key: {'en': en, 'ar': ar} for key, en, ar in SiteText.objects.values_list('key', 'en', 'ar')}
    images = {
        img.key: {'url': img.url, 'alt_en': img.alt_en, 'alt_ar': img.alt_ar}
        for img in SiteImage.objects.all()
    }
    updated = max(filter(None, [
        SiteText.objects.aggregate(m=Max('updated_at'))['m'],
        SiteImage.objects.aggregate(m=Max('updated_at'))['m'],
    ]), default=None)
    response = Response({'texts': texts, 'images': images, 'updated_at': updated})
    # Short CDN/browser cache: admin edits show up within a minute.
    response['Cache-Control'] = 'public, max-age=60, stale-while-revalidate=300'
    return response


class ContactThrottle(SimpleRateThrottle):
    """Per client IP, rate from REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['contact'].
    (ScopedRateThrottle needs a throttle_scope on the view and silently allows
    everything on function views without one.) The cache is per serverless
    instance, so this is a speed bump against spam bursts, not a hard global limit."""
    scope = 'contact'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ContactThrottle])
def public_contact(request):
    """POST /api/public/contact/  {name, email, phone?, topic?, subtopic?, message, lang?}"""
    ser = ContactCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    if ser.validated_data.pop('website', ''):
        # Honeypot filled in: a bot. Pretend success, store nothing.
        return Response({'ok': True}, status=status.HTTP_201_CREATED)
    msg = ser.save()
    transaction.on_commit(lambda: _notify_staff(msg))
    return Response({'ok': True, 'id': msg.id}, status=status.HTTP_201_CREATED)


def _notify_staff(msg):
    to = getattr(settings, 'CONTACT_NOTIFY_EMAIL', '')
    if not to or (settings.EMAIL_BACKEND == CONSOLE_EMAIL_BACKEND and not settings.DEBUG):
        return
    try:
        send_mail(
            f'[Smart Gym] New contact message: {msg.topic or "general"}',
            f'From: {msg.name} <{msg.email}> {msg.phone}\nTopic: {msg.topic} / {msg.subtopic}\n\n{msg.message}',
            settings.DEFAULT_FROM_EMAIL, [to],
        )
    except Exception:
        logger.exception('Contact notification for message #%s failed.', msg.id)


# ============================================================
# ADMIN — pages overview
# ============================================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_pages(request):
    """GET /api/admin/site-content/pages/ — counts per page for the editor's sidebar."""
    texts = {r['page']: r for r in SiteText.objects.values('page').annotate(
        total=Count('id'),
        customized=Count('id', filter=~Q(en=F('default_en')) | ~Q(ar=F('default_ar'))),
    )}
    images = {r['page']: r for r in SiteImage.objects.values('page').annotate(
        total=Count('id'),
        customized=Count('id', filter=~Q(image='') & Q(image__isnull=False)),
    )}
    return Response([
        {
            'page': page, 'label': label,
            'texts': texts.get(page, {}).get('total', 0),
            'texts_customized': texts.get(page, {}).get('customized', 0),
            'images': images.get(page, {}).get('total', 0),
            'images_customized': images.get(page, {}).get('customized', 0),
        }
        for page, label in PAGES.items()
        if page in texts or page in images
    ])


# ============================================================
# ADMIN — texts
# ============================================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_texts(request):
    """GET /api/admin/site-content/texts/?page=home&q=hero&customized=true"""
    qs = SiteText.objects.select_related('updated_by')
    if page := request.query_params.get('page'):
        qs = qs.filter(page=page)
    if q := request.query_params.get('q', '').strip():
        qs = qs.filter(Q(key__icontains=q) | Q(en__icontains=q) | Q(ar__icontains=q))
    if request.query_params.get('customized') == 'true':
        qs = qs.filter(~Q(en=F('default_en')) | ~Q(ar=F('default_ar')))
    return Response(SiteTextSerializer(qs, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def admin_text_update(request, key):
    """PATCH /api/admin/site-content/texts/<key>/  {en?, ar?}"""
    obj = get_object_or_404(SiteText, key=key)
    ser = SiteTextSerializer(obj, data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    ser.save(updated_by=request.user)
    return Response(ser.data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_text_reset(request, key):
    """POST /api/admin/site-content/texts/<key>/reset/ — back to the shipped text."""
    obj = get_object_or_404(SiteText, key=key)
    obj.en, obj.ar, obj.updated_by = obj.default_en, obj.default_ar, request.user
    obj.save()
    return Response(SiteTextSerializer(obj).data)


# ============================================================
# ADMIN — images
# ============================================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_images(request):
    """GET /api/admin/site-content/images/?page=fac"""
    qs = SiteImage.objects.select_related('updated_by')
    if page := request.query_params.get('page'):
        qs = qs.filter(page=page)
    return Response(SiteImageSerializer(qs, many=True).data)


@api_view(['POST', 'PATCH'])
@permission_classes([IsAdminUser])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def admin_image_update(request, key):
    """
    POST  /api/admin/site-content/images/<key>/  multipart {image, alt_en?, alt_ar?} — upload/replace
    PATCH /api/admin/site-content/images/<key>/  {alt_en?, alt_ar?} — alt text only
    """
    obj = get_object_or_404(SiteImage, key=key)
    ser = SiteImageUploadSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    if request.method == 'POST' and 'image' not in data:
        return Response({'image': ['Choose an image to upload.']}, status=status.HTTP_400_BAD_REQUEST)

    old = obj.image.name if obj.image else None
    if 'image' in data:
        obj.image = data['image']
    for field in ('alt_en', 'alt_ar'):
        if field in data:
            setattr(obj, field, data[field])
    obj.updated_by = request.user
    obj.save()
    if old and 'image' in data and old != obj.image.name:
        _delete_file(obj.image.storage, old)
    return Response(SiteImageSerializer(obj).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_image_reset(request, key):
    """POST /api/admin/site-content/images/<key>/reset/ — remove the upload, back to the shipped image."""
    obj = get_object_or_404(SiteImage, key=key)
    if obj.image:
        storage, name = obj.image.storage, obj.image.name
        obj.image = None
        obj.updated_by = request.user
        obj.save()
        _delete_file(storage, name)
    return Response(SiteImageSerializer(obj).data)


def _delete_file(storage, name):
    try:
        storage.delete(name)
    except Exception:
        logger.exception('Could not delete replaced site image %s', name)


# ============================================================
# ADMIN — contact messages
# ============================================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_messages(request):
    """GET /api/admin/site-content/messages/?status=new"""
    qs = ContactMessage.objects.all()
    if st := request.query_params.get('status'):
        qs = qs.filter(status=st)
    counts = dict(ContactMessage.objects.values_list('status').annotate(n=Count('id')))
    return Response({'counts': counts, 'results': ContactMessageSerializer(qs[:500], many=True).data})


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_message_detail(request, pk):
    """PATCH {status} · DELETE — /api/admin/site-content/messages/<id>/"""
    msg = get_object_or_404(ContactMessage, pk=pk)
    if request.method == 'DELETE':
        msg.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    ser = ContactMessageSerializer(msg, data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    ser.save()
    return Response(ser.data)
