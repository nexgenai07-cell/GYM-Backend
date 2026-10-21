"""
Database-backed rate limits (the cache is per serverless instance, so it can't be trusted to
count across requests on Vercel).
"""
from datetime import timedelta

from django.utils import timezone

from .models import RateEvent

KEEP = timedelta(days=1)


def client_ip(request):
    """Vercel puts the caller's address first in X-Forwarded-For (and sets X-Real-IP)."""
    real = request.META.get('HTTP_X_REAL_IP')
    if real:
        return real.strip()
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR', '')) or 'unknown'


def count(kind, key, window):
    return RateEvent.objects.filter(kind=kind, key=key, created_at__gte=timezone.now() - window).count()


def hit(kind, key):
    RateEvent.objects.create(kind=kind, key=key[:255])
    if RateEvent.objects.count() % 50 == 0:   # cheap occasional prune
        RateEvent.objects.filter(created_at__lt=timezone.now() - KEEP).delete()


def clear(kind, key):
    RateEvent.objects.filter(kind=kind, key=key).delete()
