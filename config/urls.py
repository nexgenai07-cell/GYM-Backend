from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),

    # Existing
    path('api/', include('apps.core.urls')),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/members/', include('apps.members.urls')),
    path('api/workouts/', include('apps.workouts.urls')),
    path('api/catalog/', include('apps.catalog.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/nutrition/', include('apps.nutrition.urls')),
    path('api/shop/', include('apps.shop.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/facilities/', include('apps.facilities.urls')),
    path('api/classes/', include('apps.classes.urls')),
    path('api/staff/', include('apps.staff.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/cms/', include('apps.cms.urls')),
    path('api/attendance/', include('apps.attendance.urls')),
    path('api/dashboard/', include('apps.dashboard.urls')),

        # Existing admin dashboard API (members, machines, finance, analytics…)
    path('api/admin/', include('apps.admin_api.urls')),

    # Public site registration pipeline
    path('api/public/', include('apps.public_api.urls')),

    # Admin approvals + gym-entry lookup (kept under a distinct prefix
    # so it doesn't collide with apps.admin_api.urls)
    path('api/admin/registrations-api/', include('apps.public_api.admin_urls')),
]
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)