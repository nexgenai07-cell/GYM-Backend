from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from datetime import timedelta

from . import ratelimit
from .models import User
from .ratelimit import client_ip
from .serializers import (
    UserSerializer,
    CustomTokenObtainPairSerializer,
    ProfileUpdateSerializer,
    ChangePasswordSerializer,
)


# ============================================
# LOGIN (JWT)
# ============================================
class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Body: { "email": "...", "password": "..." }
    Returns: { access, refresh, user }
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

    # 5 wrong passwords for one email, or 30 from one IP, in 15 minutes → locked for the rest of the window.
    WINDOW = timedelta(minutes=15)
    PER_EMAIL, PER_IP = 5, 30

    def post(self, request, *args, **kwargs):
        email = str(request.data.get('email') or '').strip().lower()
        ip = client_ip(request)
        locked = ((email and ratelimit.count('login_email', email, self.WINDOW) >= self.PER_EMAIL)
                  or ratelimit.count('login_ip', ip, self.WINDOW) >= self.PER_IP)
        if locked:
            return Response({'detail': 'Too many sign-in attempts. Wait 15 minutes and try again.'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed:   # wrong email or password
            if email:
                ratelimit.hit('login_email', email)
            ratelimit.hit('login_ip', ip)
            raise
        if email:
            ratelimit.clear('login_email', email)
        return response


# ============================================
# REGISTER
# ============================================
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    POST /api/auth/register/ — closed. Accounts are created when the gym approves a paid
    signup from the website (POST /api/public/register/ → admin approval).
    """
    return Response({'detail': 'Join on the Smart Gym website — your account is created when your membership is approved.'},
                    status=status.HTTP_403_FORBIDDEN)


# ============================================
# GET / UPDATE CURRENT USER
# ============================================
@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    GET  /api/auth/me/  → return current user
    PATCH /api/auth/me/ → update current user profile
    """
    if request.method == 'GET':
        return Response(UserSerializer(request.user).data)

    serializer = ProfileUpdateSerializer(
        request.user,
        data=request.data,
        partial=True,
    )
    if serializer.is_valid():
        serializer.save()
        return Response(UserSerializer(request.user).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# CHANGE PASSWORD
# ============================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    POST /api/auth/change-password/
    Body: { old_password, new_password, new_password_confirm }
    """
    serializer = ChangePasswordSerializer(
        data=request.data,
        context={'request': request},
    )
    if serializer.is_valid():
        serializer.save()
        return Response({'detail': 'Password updated successfully.'})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# LOGOUT
# ============================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    POST /api/auth/logout/
    Body: { refresh: "<refresh_token>" }
    Blacklists the refresh token.
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'detail': 'Logged out successfully.'})
    except Exception as e:
        return Response(
            {'detail': 'Invalid or expired token.'},
            status=status.HTTP_400_BAD_REQUEST,
        )