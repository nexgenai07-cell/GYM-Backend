from django.urls import path
from . import views

app_name = 'classes'

urlpatterns = [
    path('schedule/', views.classes_schedule, name='schedule'),
    path('stats/', views.classes_stats, name='stats'),
]