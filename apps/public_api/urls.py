from django.urls import path
from . import views

app_name = 'public_api'

urlpatterns = [
    # Public read
    path('plans/',      views.public_plans,      name='plans'),
    path('courses/',    views.public_courses,    name='courses'),
    path('facilities/', views.public_facilities, name='facilities'),
    path('trainers/',   views.public_trainers,   name='trainers'),
    path('articles/',   views.public_articles,   name='articles'),

    # Public register
    path('register/',                       views.public_register,         name='register'),
    path('register/<int:reg_id>/status/',   views.public_register_status,  name='register-status'),
    path('register/<int:reg_id>/payment/',  views.public_payment_webhook,  name='register-payment'),
]