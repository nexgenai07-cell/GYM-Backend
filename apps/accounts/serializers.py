from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


# ============================================
# USER SERIALIZERS
# ============================================
class UserSerializer(serializers.ModelSerializer):
    """Public user info — safe to return to any client."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'phone', 'role', 'avatar', 'date_of_birth',
            'is_verified', 'created_at',
        ]
        read_only_fields = ['id', 'email', 'role', 'is_verified', 'created_at']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


# ============================================
# REGISTRATION
# ============================================
class RegisterSerializer(serializers.ModelSerializer):
    """Register a new member."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({
                'password': 'Passwords do not match.',
            })
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value.lower()

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Username already taken.')
        return value

    def create(self, validated_data):
        # Members only can self-register
        user = User.objects.create_user(
            role='member',
            **validated_data,
        )
        return user


# ============================================
# LOGIN (JWT)
# ============================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends default JWT serializer to include user data in response.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['email'] = user.email
        token['role'] = user.role
        token['full_name'] = f"{user.first_name} {user.last_name}".strip() or user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Add user data to response
        data['user'] = UserSerializer(self.user).data
        return data


# ============================================
# PROFILE UPDATE
# ============================================
class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Allow updating the current user's profile."""

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone',
            'avatar', 'date_of_birth',
        ]


# ============================================
# PASSWORD CHANGE
# ============================================
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
    )
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password': 'New passwords do not match.',
            })
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user