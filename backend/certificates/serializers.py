from rest_framework import serializers

from .models import Certificate, CertificateTemplate


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = [
            'id',
            'user',
            'course',
            'issued_at',
            'certificate_number',
            'verification_token',
            'pdf_file',
            'expires_at',
        ]
        read_only_fields = fields


class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = [
            'id',
            'name',
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
