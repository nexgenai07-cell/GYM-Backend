from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.my_notifications, name='list'),
    path('unread-count/', views.unread_count, name='unread-count'),
    path('<int:notification_id>/read/', views.mark_read, name='mark-read'),
    path('mark-all-read/', views.mark_all_read, name='mark-all-read'),
    path('<int:notification_id>/', views.delete_notification, name='delete'),
    path('preferences/', views.my_preferences, name='preferences'),
]