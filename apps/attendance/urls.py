from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('summary/', views.summary, name='summary'),
    path('check-ins/', views.check_ins, name='check-ins'),
    path('check-ins/<int:check_in_id>/check-out/', views.check_out, name='check-out'),
    path('ledger/', views.ledger, name='ledger'),
    path('ledger/export/', views.ledger_export, name='ledger-export'),
    path('heatmap/', views.heatmap, name='heatmap'),
    path('milestones/', views.milestones, name='milestones'),
    path('milestones/<int:milestone_id>/claim/', views.claim_milestone, name='claim-milestone'),
    path('hourly/', views.hourly, name='hourly'),
    path('arenas/', views.arenas, name='arenas'),
]