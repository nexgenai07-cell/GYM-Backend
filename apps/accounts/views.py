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
            left = self.PER_EMAIL - ratelimit.count('login_email', email, self.WINDOW) if email else 0
            msg = 'Wrong email or password. Check both and try again.'
            if 0 < left <= 2:
                msg += f' {left} attempt{"s" if left != 1 else ""} left before sign-in is paused for 15 minutes.'
            elif left <= 0:
                msg = 'Too many sign-in attempts. Wait 15 minutes and try again, or reset your password.'
            return Response({'detail': msg}, status=status.HTTP_401_UNAUTHORIZED)
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
# FORGOT / RESET PASSWORD
# ============================================
RESET_PER_EMAIL = 3          # reset emails per address per hour
RESET_PER_IP = 10


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    POST /api/auth/password/forgot/  { email, admin?: bool }
    Emails a one-time reset link (valid PASSWORD_RESET_TIMEOUT, 3 days by default). The answer is
    the same whether or not the email has an account, so it can't be used to find accounts.
    """
    import logging
    from django.conf import settings
    from django.contrib.auth.tokens import default_token_generator
    from django.core.mail import send_mail
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    from apps.core.validators import email_error
    from apps.members.services import member_portal_url

    email = str(request.data.get('email') or '').strip().lower()
    msg = email_error(email)
    if msg:
        return Response({'email': msg}, status=status.HTTP_400_BAD_REQUEST)
    done = Response({'detail': 'If an account exists for this email, a reset link is on its way. '
                               'Check your inbox (and spam folder).'})
    ip = client_ip(request)
    window = timedelta(hours=1)
    if ratelimit.count('reset_email', email, window) >= RESET_PER_EMAIL or ratelimit.count('reset_ip', ip, window) >= RESET_PER_IP:
        return Response({'detail': 'Too many reset requests. Please try again in an hour.'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)
    ratelimit.hit('reset_email', email)
    ratelimit.hit('reset_ip', ip)

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        return done
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    staff = user.role in ('admin', 'manager')
    link = f"{member_portal_url()}/{'admin/' if staff else ''}reset-password?uid={uid}&token={token}"
    name = user.first_name or user.email
    try:
        send_mail(
            'Smart Gym — reset your password · إعادة تعيين كلمة المرور',
            f"Hi {name},\n\nSomeone (hopefully you) asked to reset your Smart Gym password.\n"
            f"Open this link to choose a new one (it works once and expires in 3 days):\n\n  {link}\n\n"
            "If you didn't ask for this, ignore this email — your password stays the same.\n— Smart Gym\n\n"
            "────────────\n\n"
            f"مرحبًا {name}،\n\nطُلب إعادة تعيين كلمة مرور حسابك في سمارت جيم.\n"
            f"افتح الرابط لاختيار كلمة مرور جديدة (يعمل مرة واحدة وينتهي خلال 3 أيام):\n\n  {link}\n\n"
            "إذا لم تطلب ذلك فتجاهل هذه الرسالة.\n— سمارت جيم",
            settings.DEFAULT_FROM_EMAIL, [user.email],
        )
    except Exception:   # noqa: BLE001
        logging.getLogger(__name__).exception('Password reset email to %s failed.', user.email)
        return Response({'detail': 'We couldn’t send the email right now. Please try again later or contact the front desk.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return done


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    POST /api/auth/password/reset/  { uid, token, new_password, new_password_confirm }
    """
    from django.contrib.auth.password_validation import validate_password
    from django.contrib.auth.tokens import default_token_generator
    from django.core.exceptions import ValidationError
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    bad_link = Response({'detail': 'This reset link is invalid or has already been used. Ask for a new one.'},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(str(request.data.get('uid') or ''))), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return bad_link
    if not default_token_generator.check_token(user, str(request.data.get('token') or '')):
        return bad_link

    new, confirm = str(request.data.get('new_password') or ''), str(request.data.get('new_password_confirm') or '')
    errors = {}
    if not new:
        errors['new_password'] = 'Enter a new password.'
    else:
        try:
            validate_password(new, user)
        except ValidationError as e:
            errors['new_password'] = ' '.join(e.messages)
    if new and new != confirm:
        errors['new_password_confirm'] = 'The two passwords don’t match.'
    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new)
    user.must_change_password = False
    user.save(update_fields=['password', 'must_change_password'])
    ratelimit.clear('login_email', user.email.lower())     # a locked-out user can sign in again
    return Response({'detail': 'Password changed. You can sign in now.',
                     'login_path': '/admin/login' if user.role in ('admin', 'manager') else '/login'})


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