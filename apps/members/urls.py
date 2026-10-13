# apps/members/urls.py — add one line

from django.urls import path
from . import views

app_name = 'members'

urlpatterns = [
    path('plans/', views.plans_list, name='plans-list'),
    path('membership/', views.my_membership, name='my-membership'),
    path('check-ins/', views.check_ins, name='check-ins'),
    path('check-ins/<int:check_in_id>/check-out/', views.check_out, name='check-out'),

    # ⬇️ NEW: QR verification endpoint
    path('verify/<int:member_id>/', views.verify_member, name='verify-member'),
]