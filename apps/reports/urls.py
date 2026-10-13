from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('templates/', views.templates_list, name='templates'),
    path('generate/', views.generate_report, name='generate'),
    path('history/', views.history_list, name='history'),
    path('history/<str:report_id>/', views.report_detail, name='detail'),
    path('history/<str:report_id>/delete/', views.delete_report, name='delete'),
    path('history/<str:report_id>/download/', views.download_report, name='download'),
]