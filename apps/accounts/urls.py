from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'accounts'

urlpatterns = [
    # Auth
    path('register/', views.register, name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', views.logout, name='logout'),

    # User
    path('me/', views.me, name='me'),
    path('change-password/', views.change_password, name='change-password'),
]