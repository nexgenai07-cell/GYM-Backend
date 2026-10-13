from django.urls import path
from . import views

app_name = 'workouts'

urlpatterns = [
    # Exercises catalog
    path('exercises/', views.exercises_list, name='exercises-list'),
    path('exercises/qr/<str:qr_tag_id>/', views.exercise_by_qr, name='exercise-by-qr'),

    # Workouts
    path('', views.workouts_list, name='workouts-list'),
    path('<int:workout_id>/', views.workout_detail, name='workout-detail'),
    path('<int:workout_id>/complete/', views.workout_complete, name='workout-complete'),
    path('<int:workout_id>/exercises/', views.add_exercise_to_workout, name='add-exercise'),

    # Sets
    path('exercises/<int:workout_exercise_id>/sets/', views.log_set, name='log-set'),

    # PRs
    path('prs/', views.my_prs, name='my-prs'),

    # Analytics
    path('stats/', views.workout_stats, name='workout-stats'),

    # Templates
    path('templates/', views.templates_list, name='templates-list'),

     path('exercises/<int:exercise_id>/quick-log/', views.quick_log_set, name='quick-log'),
]