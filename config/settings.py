"""
Django settings for Smart Gym Backend.
"""

import os
from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured
import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# SECURITY
# ============================================
# No default: a missing SECRET_KEY must crash startup, not fall back to a guessable key.
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())


# ============================================
# APPLICATIONS
# ============================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    # Local apps
    'apps.core',
    'apps.accounts',
    'apps.members',
    'apps.workouts',
    'apps.catalog',
    'apps.payments',
    'apps.nutrition',
    'apps.shop',
    'apps.notifications',
    'apps.admin_api',
    'apps.facilities',
    'apps.classes',
    'apps.staff',
    'apps.reports',
    'apps.cms',
    'apps.attendance',
    'apps.dashboard',
    'apps.public_api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',           # first
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',      # <-- must be here
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ============================================
# DATABASE
# ============================================
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
        conn_max_age=600,
        ssl_require=not DEBUG,
    )
}

# Safety: DEBUG=True means local development, and local development must never
# touch the production (Neon) database. Crash instead of silently using it.
# A deliberate production task needs DEBUG=False in that shell.
if DEBUG and 'neon.tech' in str(DATABASES['default'].get('HOST', '')):
    raise ImproperlyConfigured(
        'DEBUG=True with the production Neon database. Local work must use '
        'DATABASE_URL=sqlite:///db.sqlite3 (check .env and any "set DATABASE_URL" in this window). '
        'For a deliberate production task, also set DEBUG=False.'
    )

# ============================================
# AUTH
# ============================================
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================
# INTERNATIONALIZATION
# ============================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============================================
# STATIC & MEDIA
# ============================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles_build' / 'static'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Media uploads (registration photos): local disk by default; Cloudflare R2
# only when R2_ACCESS_KEY_ID is set.
R2_ACCESS_KEY_ID     = config('R2_ACCESS_KEY_ID', default='')
R2_SECRET_ACCESS_KEY = config('R2_SECRET_ACCESS_KEY', default='')
R2_BUCKET_NAME       = config('R2_BUCKET_NAME', default='')
R2_ENDPOINT_URL      = config('R2_ENDPOINT_URL', default='')
USE_R2 = bool(R2_ACCESS_KEY_ID)

if USE_R2 and not all([R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_ENDPOINT_URL]):
    raise ImproperlyConfigured(
        'R2_ACCESS_KEY_ID is set, so R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME and '
        'R2_ENDPOINT_URL must be set too (or unset R2_ACCESS_KEY_ID to use local storage).'
    )

if not USE_R2 and os.environ.get('VERCEL'):
    # Vercel's deployment dir is read-only; /tmp is writable but wiped on cold
    # start and not shared between instances — uploads there are temporary.
    MEDIA_ROOT = Path('/tmp/media')
    # warnings, not logging — LOGGING isn't configured yet while settings load.
    import warnings
    warnings.warn('R2 not configured on Vercel: media uploads go to /tmp and will be lost.')

if USE_R2:
    DEFAULT_STORAGE = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": R2_ACCESS_KEY_ID,
            "secret_key": R2_SECRET_ACCESS_KEY,
            "bucket_name": R2_BUCKET_NAME,
            "endpoint_url": R2_ENDPOINT_URL,
            "region_name": "auto",
            "signature_version": "s3v4",
            "default_acl": None,        # R2 ignores ACLs; bucket stays private
            "querystring_auth": True,   # photos served via signed URLs
            "querystring_expire": 3600,
            "file_overwrite": False,
        },
    }
else:
    DEFAULT_STORAGE = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
    os.makedirs(MEDIA_ROOT, exist_ok=True)

# Django 5.1+ / 6.x unified storage config.
# BOTH keys are required — "default" handles FileField/ImageField
# uploads, "staticfiles" handles collectstatic.
STORAGES = {
    "default": DEFAULT_STORAGE,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Whitenoise config — makes collectstatic run at every boot on Vercel
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_ALLOW_ALL_ORIGINS = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# DJANGO REST FRAMEWORK
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

# ============================================
# JWT
# ============================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ============================================
# CSRF
# ============================================
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://gym-member-and-admin.vercel.app,https://gym-backend-xi-seven.vercel.app',
    cast=Csv(),
)

# ============================================
# CORS
# ============================================
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173',
    cast=Csv()
)

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ============================================
# CUSTOM SETTINGS
# ============================================
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')


# ============================================
# PAYMENT GATEWAY
# ============================================
# Moyasar (Mada / STC Pay). The secret key never leaves the backend.
# Missing keys only break the payment endpoints (see apps/public_api/moyasar.py),
# not the whole API.
MOYASAR_SECRET_KEY      = config('MOYASAR_SECRET_KEY', default='')
MOYASAR_PUBLISHABLE_KEY = config('MOYASAR_PUBLISHABLE_KEY', default='')
MOYASAR_WEBHOOK_SECRET  = config('MOYASAR_WEBHOOK_SECRET', default='')
MOYASAR_API_URL         = config('MOYASAR_API_URL', default='https://api.moyasar.com/v1')

# ============================================
# EMAIL (stub)
# ============================================
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@smartgym.local')


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# ============================================
# PRODUCTION SECURITY
# ============================================
if not DEBUG:
    # Required behind Vercel's proxy so Django knows the request is HTTPS
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Cookies only sent over HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS — tells browsers to always use HTTPS
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

 