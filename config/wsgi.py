"""
WSGI config for Smart Gym Backend.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# ─────────────────────────────────────────────────────────
# Vercel-friendly: collect static files at cold start
# if STATIC_ROOT is missing or empty.
# Whitenoise serves them afterward.
# ─────────────────────────────────────────────────────────
if os.environ.get('VERCEL'):
    try:
        from django.conf import settings
        from django.core.management import call_command

        static_root = str(settings.STATIC_ROOT)
        needs_collect = (
            not os.path.isdir(static_root)
            or not os.listdir(static_root)
        )
        if needs_collect:
            call_command('collectstatic', '--noinput', verbosity=0)
    except Exception as exc:
        # Never crash the app on static collection failure
        print(f'[wsgi] collectstatic skipped: {exc}')