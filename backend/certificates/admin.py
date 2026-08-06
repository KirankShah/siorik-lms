from django.contrib import admin

from .models import Certificate, CertificateTemplate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        'certificate_number',
        'user',
        'course',
        'issued_at',
        'expires_at',
        'verification_token',
    )
    list_filter = ('course',)
    search_fields = ('certificate_number', 'user__email', 'course__title', 'verification_token')
    readonly_fields = ('certificate_number', 'verification_token', 'issued_at', 'pdf_file')


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'created_at', 'updated_at')
    list_filter = ('is_default',)
    search_fields = ('name',)
