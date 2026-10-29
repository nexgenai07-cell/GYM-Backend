from django.utils.text import slugify
from rest_framework import serializers

from apps.members.models import MembershipPlan

from .models import ContactMessage, SiteImage, SiteItem, SiteText

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


class SiteItemSerializer(serializers.ModelSerializer):
    """Admin view of a collection item."""
    image_url = serializers.CharField(read_only=True)
    uploaded_image_url = serializers.SerializerMethodField()
    updated_by_email = serializers.EmailField(source='updated_by.email', read_only=True, allow_null=True)

    class Meta:
        model = SiteItem
        fields = ['id', 'collection', 'slug', 'order', 'is_active', 'data', 'image_url',
                  'uploaded_image_url', 'default_image_url', 'created_at', 'updated_at', 'updated_by_email']
        read_only_fields = fields

    def get_uploaded_image_url(self, obj):
        return obj.image.url if obj.image else None


def public_item(item, include=None):
    """Public shape of an item; `include` limits the data fields returned."""
    data = item.data if include is None else {k: v for k, v in item.data.items() if k in include}
    return {'id': item.id, 'slug': item.slug, 'data': data, 'image_url': item.image_url}


class ContactCreateSerializer(serializers.ModelSerializer):
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)   # honeypot

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'topic', 'subtopic', 'message', 'lang', 'website']

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError('Tell us a bit more — at least 10 characters.')
        return value

    def validate_name(self, value):
        from apps.core.validators import person_name_error
        value = ' '.join(value.split())
        msg = person_name_error(value, 'Name', max_length=120)
        if msg:
            raise serializers.ValidationError(msg)
        return value

    def validate_email(self, value):
        from apps.core.validators import email_error
        value = value.strip().lower()
        msg = email_error(value)
        if msg:
            raise serializers.ValidationError(msg)
        return value

    def validate_phone(self, value):
        from apps.core.phone import MESSAGE, normalize_saudi_mobile
        value = (value or '').strip()
        if not value:
            return ''
        phone = normalize_saudi_mobile(value)
        if phone is None:
            raise serializers.ValidationError(MESSAGE)
        return phone


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'phone', 'topic', 'subtopic', 'message', 'lang', 'status', 'created_at']
        read_only_fields = ['id', 'name', 'email', 'phone', 'topic', 'subtopic', 'message', 'lang', 'created_at']


class AdminPlanSerializer(serializers.ModelSerializer):
    """Membership plans as edited from the admin portal (public pricing + signup)."""
    registrations = serializers.IntegerField(source='registrations.count', read_only=True)

    class Meta:
        model = MembershipPlan
        fields = ['id', 'name', 'display_name', 'display_name_ar', 'description', 'description_ar',
                  'price_monthly', 'price_annual', 'features', 'features_ar', 'session_limit_minutes',
                  'video_access', 'is_active', 'registrations', 'created_at']
        read_only_fields = ['id', 'registrations', 'created_at']

    def validate_name(self, value):
        value = slugify(value)
        if not value:
            raise serializers.ValidationError('Use letters, numbers and dashes.')
        qs = MembershipPlan.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError(f'The code “{value}” is already used by another plan.')
        return value

    def _unique_display(self, value, field, label):
        from apps.core.validators import duplicate_error
        value = ' '.join(str(value or '').split())
        if field == 'display_name' and len(value) < 2:
            raise serializers.ValidationError('Plan name must be at least 2 characters.')
        msg = duplicate_error(MembershipPlan.objects.all(), field, value, label,
                              exclude_id=self.instance.id if self.instance else None)
        if msg:
            raise serializers.ValidationError(msg)
        return value

    def validate_display_name(self, value):
        return self._unique_display(value, 'display_name', 'A plan named')

    def validate_display_name_ar(self, value):
        return self._unique_display(value, 'display_name_ar', 'A plan with the Arabic name') if value else value

    def _validate_features(self, value):
        value = value or []
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise serializers.ValidationError('A list of short texts.')
        if len(value) > 20:
            raise serializers.ValidationError('At most 20 features.')
        return [v.strip()[:120] for v in value if v.strip()]

    validate_features = _validate_features
    validate_features_ar = _validate_features

    def validate(self, attrs):
        for field in ('price_monthly', 'price_annual'):
            if field in attrs and attrs[field] <= 0:
                raise serializers.ValidationError({field: 'Must be more than 0.'})
        return attrs
