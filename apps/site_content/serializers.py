from rest_framework import serializers

from .models import ContactMessage, SiteImage, SiteText

MAX_IMAGE_BYTES = 4 * 1024 * 1024        # Vercel rejects request bodies over 4.5 MB
IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


class SiteTextSerializer(serializers.ModelSerializer):
    is_customized = serializers.BooleanField(read_only=True)
    updated_by_email = serializers.EmailField(source='updated_by.email', read_only=True, allow_null=True)

    class Meta:
        model = SiteText
        fields = ['key', 'page', 'en', 'ar', 'default_en', 'default_ar',
                  'is_customized', 'updated_at', 'updated_by_email']
        read_only_fields = ['key', 'page', 'default_en', 'default_ar', 'updated_at']


class SiteImageSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)
    uploaded_url = serializers.SerializerMethodField()
    is_customized = serializers.BooleanField(read_only=True)
    updated_by_email = serializers.EmailField(source='updated_by.email', read_only=True, allow_null=True)

    class Meta:
        model = SiteImage
        fields = ['key', 'page', 'label', 'url', 'uploaded_url', 'default_url', 'alt_en', 'alt_ar',
                  'is_customized', 'updated_at', 'updated_by_email']
        read_only_fields = ['key', 'page', 'label', 'default_url', 'updated_at']

    def get_uploaded_url(self, obj):
        return obj.image.url if obj.image else None


class SiteImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=False)
    alt_en = serializers.CharField(max_length=200, required=False, allow_blank=True)
    alt_ar = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate_image(self, value):
        if value.size > MAX_IMAGE_BYTES:
            raise serializers.ValidationError('Image must be under 4 MB.')
        if getattr(value, 'content_type', None) not in IMAGE_TYPES:
            raise serializers.ValidationError('Use a JPEG, PNG or WebP image.')
        return value


class ContactCreateSerializer(serializers.ModelSerializer):
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)   # honeypot

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'topic', 'subtopic', 'message', 'lang', 'website']

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError('Please write a few words.')
        return value


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'phone', 'topic', 'subtopic', 'message', 'lang', 'status', 'created_at']
        read_only_fields = ['id', 'name', 'email', 'phone', 'topic', 'subtopic', 'message', 'lang', 'created_at']
