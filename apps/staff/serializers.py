from rest_framework import serializers
from .models import StaffProfile


class StaffProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    avatar = serializers.SerializerMethodField()
    shift_display = serializers.CharField(read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            'id', 'user', 'user_name', 'user_email', 'role',
            'avatar', 'department', 'status',
            'shift_start', 'shift_end', 'shift_display',
            'permissions_count', 'joined_at', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_avatar(self, obj):
        initials = ''.join([n[0] for n in obj.user.full_name.split()[:2]]).upper()
        return initials or 'ST'