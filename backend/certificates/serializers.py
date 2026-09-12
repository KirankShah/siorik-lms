from rest_framework import serializers

from accounts.models import Organization

from .models import Certificate, CertificateTemplate
from .services import _learning_path_completion_title


class CertificateSerializer(serializers.ModelSerializer):
    # `course` still just anchors the certificate to the last course in the
    # learner's path (template resolution/record-keeping — see
    # certificates.services.generate_learning_path_certificate); course_title
    # is kept for reference, but `title` is what the learner-facing
    # Certificates page card should show, since it's the same "<Tier>
    # Learning Path" text actually printed on the certificate PDF.
    course_title = serializers.CharField(source='course.title', read_only=True)
    title = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            'id',
            'user',
            'course',
            'course_title',
            'title',
            'issued_at',
            'certificate_number',
            'verification_token',
            'pdf_file',
            'expires_at',
        ]
        read_only_fields = fields

    def get_title(self, certificate):
        return _learning_path_completion_title(certificate.user)


class CertificateTemplateSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), allow_null=True, required=False,
    )

    class Meta:
        model = CertificateTemplate
        fields = [
            'id',
            'name',
            'organization',
            'background_image',
            'is_default',
            'staff_name_x_percent',
            'staff_name_y_percent',
            'staff_name_font_size',
            'staff_name_color',
            'staff_name_font_file',
            'staff_name_text_align',
            'course_name_x_percent',
            'course_name_y_percent',
            'course_name_font_size',
            'course_name_color',
            'course_name_font_file',
            'course_name_text_align',
            'issue_date_x_percent',
            'issue_date_y_percent',
            'issue_date_font_size',
            'issue_date_color',
            'issue_date_font_file',
            'issue_date_text_align',
            'qr_code_x_percent',
            'qr_code_y_percent',
            'qr_code_size_percent',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        organization = attrs.get('organization', getattr(self.instance, 'organization', None))
        is_default = attrs.get('is_default', getattr(self.instance, 'is_default', False))
        if is_default and organization is not None:
            raise serializers.ValidationError(
                {'is_default': 'Only a platform-level template (no organization) can be the default.'}
            )

        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and user.role in (user.Role.ORG_ADMIN, user.Role.INSTRUCTOR):
            if organization is None:
                raise serializers.ValidationError(
                    {'organization': 'Only a platform administrator can manage the platform-level template.'}
                )
            if organization.id != user.organization_id:
                raise serializers.ValidationError(
                    {'organization': "You can only manage your own organization's certificate template."}
                )
        return attrs
