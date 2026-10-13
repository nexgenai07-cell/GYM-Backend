from django.urls import path
from . import views

app_name = 'admin_registrations'

urlpatterns = [
    # Registrations
    path('registrations/',                      views.admin_registrations,           name='list'),
    path('registrations/stats/',                views.admin_registration_stats,      name='stats'),
    path('registrations/bulk-approve/',         views.admin_bulk_approve,            name='bulk-approve'),
    path('registrations/<int:reg_id>/',         views.admin_registration_detail,     name='detail'),
    path('registrations/<int:reg_id>/approve/', views.admin_approve_registration,    name='approve'),
    path('registrations/<int:reg_id>/reject/',  views.admin_reject_registration,     name='reject'),

    # Member lookup + entry
    path('members/lookup/',                     views.admin_member_lookup,           name='lookup'),
    path('members/<int:member_id>/face-verify/', views.admin_member_face_verify,     name='face-verify'),
    path('members/<int:member_id>/check-in/',   views.admin_check_in,                name='check-in'),
    path('check-ins/<int:check_in_id>/check-out/', views.admin_check_out,            name='check-out'),
]