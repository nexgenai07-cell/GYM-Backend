from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    # Trainers
    path('trainers/', views.trainers_list, name='trainers-list'),
    path('trainers/<int:trainer_id>/', views.trainer_detail, name='trainer-detail'),
    path('trainers/<int:trainer_id>/review/', views.review_trainer, name='review-trainer'),

    # Courses
    path('courses/', views.courses_list, name='courses-list'),
    path('courses/categories/', views.course_categories, name='course-categories'),
    path('courses/<int:course_id>/', views.course_detail, name='course-detail'),
    path('courses/<int:course_id>/review/', views.review_course, name='review-course'),

    # Enrollments
    path('enrollments/', views.my_enrollments, name='my-enrollments'),
    path('enrollments/<int:enrollment_id>/modules/<int:module_id>/complete/',
         views.complete_module, name='complete-module'),

    # 1:1 Sessions
    path('sessions/', views.my_sessions, name='my-sessions'),
    path('sessions/<int:session_id>/cancel/', views.cancel_session, name='cancel-session'),

    # Course player
    path('courses/<int:course_id>/player/', views.course_player, name='course-player'),
    path('next-workout/', views.next_workout_suggestion, name='next-workout'),
]