from django.urls import path
from . import views

app_name = 'facilities'

urlpatterns = [
    path('', views.facilities_list, name='list'),
    path('stats/', views.facilities_stats, name='stats'),
]