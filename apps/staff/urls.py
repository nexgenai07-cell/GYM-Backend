from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.staff_list, name='list'),
    path('stats/', views.staff_stats, name='stats'),
    path('<int:staff_id>/', views.staff_detail, name='detail'),
]