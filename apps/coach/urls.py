from django.urls import path

from . import views

app_name = 'coach'

urlpatterns = [
    path('me/', views.me, name='me'),
    path('me/photo/', views.me_photo, name='me-photo'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('hours/', views.hours, name='hours'),
    path('sessions/', views.sessions, name='sessions'),
    path('sessions/<int:session_id>/status/', views.session_status, name='session-status'),
    path('courses/', views.courses, name='courses'),
    path('courses/<int:course_id>/', views.course_detail, name='course-detail'),
    path('courses/<int:course_id>/submit/', views.course_submit, name='course-submit'),
    path('courses/<int:course_id>/cover/', views.course_cover, name='course-cover'),
    path('students/', views.students, name='students'),
    path('classes/', views.classes, name='classes'),
    path('reviews/', views.reviews, name='reviews'),
    path('earnings/', views.earnings, name='earnings'),
    path('machines/', views.machines, name='machines'),
    path('videos/', views.videos, name='videos'),
    path('videos/<int:video_id>/', views.video_detail, name='video-detail'),
]
