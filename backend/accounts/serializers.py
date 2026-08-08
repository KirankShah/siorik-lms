from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Organization, User


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'logo', 'is_active']


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'organization',
            'phone_number',
            'designation',
            'is_active',
            'is_demo',
            'must_reset_password',
        ]
        read_only_fields = fields


class DemoUserCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.filter(is_active=True))
    designation = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')


class SetPasswordSerializer(serializers.Serializer):
    """
    Backs the forced-reset dialog shown to any account with must_reset_password
    set (see accounts.views.SetPasswordView). No current_password field — the
    caller already proved they know it by logging in with it, and this
    endpoint has no other consumer, so re-verifying it here would just be
    redundant friction in the dialog.
    """

    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value
