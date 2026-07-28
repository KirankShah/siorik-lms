from rest_framework import serializers

from .models import Certificate


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
