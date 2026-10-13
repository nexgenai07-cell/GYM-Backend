"""
WSGI config for Smart Gym Backend.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# ─────────────────────────────────────────────────────────
# Vercel-friendly: run collectstatic at cold start if
# static files are missing. Whitenoise serves them after.
# ─────────────────────────────────────────────────────────
if os.environ.get('VERCEL'):
    try:
        from django.conf import settings
        if not os.path.isdir(str(settings.STATIC_ROOT)) or not os.listdir(str(settings.STATIC_ROOT)):
            from django.core.management import call_command
            call_command('collectstatic', '--noinput', verbosity=0)
    except Exception:
        pass  # never crash the app on static collection failure