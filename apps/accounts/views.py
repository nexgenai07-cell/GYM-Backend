from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    UserSerializer,
    RegisterSerializer,
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


# ============================================
# REGISTER
# ============================================
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    POST /api/auth/register/
    Body: { email, username, password, password_confirm, first_name, last_name, phone }
    Returns: { user, access, refresh }
    """
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        # Generate tokens immediately
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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