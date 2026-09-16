from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.text import slugify
from rest_framework import serializers

from .models import Organization, User
from .staff_import import ACCEPTED_LEVEL_LABELS
from .staff_import import resolve_assessment_level as _resolve_staff_level


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'logo', 'is_active']
        extra_kwargs = {'slug': {'required': False}}

    def validate_name(self, value):
        value = value.strip()
        existing = Organization.objects.filter(name__iexact=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError('An organization with this name already exists.')
        return value

    def validate(self, attrs):
        # slug is a required-unique model field, but making the caller invent
        # one is needless friction for the common case — auto-derive it from
        # name when omitted, disambiguating against any existing collision.
        if not attrs.get('slug'):
            base_slug = slugify(attrs.get('name', ''))
            slug = base_slug
            suffix = 2
            while Organization.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{suffix}'
                suffix += 1
            attrs['slug'] = slug
        return attrs


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
            'corporate_title',
            'functional_title',
            'branch_department',
            'assessment_level',
            'is_active',
            'is_demo',
            'must_reset_password',
            'preferred_narration_language',
        ]
        read_only_fields = fields


class UserPreferenceSerializer(serializers.ModelSerializer):
    """Backs MeView's PATCH — the only self-service field a user can change here."""

    class Meta:
        model = User
        fields = ['preferred_narration_language']


class DemoUserCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.filter(is_active=True))
    designation = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')


class StaffCreateSerializer(serializers.Serializer):
    """
    Individual counterpart to the staff-enrollment bulk upload
    (accounts.views.StaffEnrollmentViewSet.create) — same fields as the CSV
    template row minus Organization, which the view supplies itself (the
    caller's own organization for ORG_ADMIN, or the `organization` field
    below for PLATFORM_ADMIN, who administers more than one).
    """

    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True), required=False
    )
    corporate_title = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    functional_title = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    branch_department = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    assessment_level = serializers.CharField(max_length=50)

    def validate_assessment_level(self, value):
        resolved = _resolve_staff_level(value)
        if resolved is None:
            raise serializers.ValidationError(
                f'Assessment Level "{value}" must be one of: ' + ', '.join(ACCEPTED_LEVEL_LABELS) + '.'
            )
        return str(resolved)


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


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Input for the self-service "forgot password" request step. Deliberately
    carries no information about whether the email matched an account — see
    accounts.views.PasswordResetRequestView, which always responds the same
    way regardless, to avoid leaking account existence.
    """

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Input for the self-service "forgot password" confirm step. uid/token
    come from the link in accounts.services.send_password_reset_email;
    validate() resolves and attaches the target user (as attrs['user']) so
    the view doesn't have to re-decode them.
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        invalid = serializers.ValidationError(
            {'detail': 'This password reset link is invalid or has expired.'}
        )
        try:
            user_pk = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=user_pk, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise invalid
        if not default_token_generator.check_token(user, attrs['token']):
            raise invalid

        attrs['user'] = user
        return attrs
