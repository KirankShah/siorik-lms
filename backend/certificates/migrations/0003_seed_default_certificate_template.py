from django.db import migrations

# Coordinates/color below were measured directly off backend/media/certificates/
# certificate_template.png (2000x1414px) by sampling the gold <STAFF NAME> glyph
# pixels and the dark placeholder-text row bands for <Course Name> / <Date> — see
# the CertificateTemplate calibration tool for fine-tuning these further.
#
# The source PNG has the <STAFF NAME> / <Course Name > / <Date> placeholder text
# baked directly into its pixels, which would show through underneath whatever
# generate_certificate() draws on top. certificate_template_clean.png is a
# one-time-generated copy with those three regions patched over with the
# sampled paper background color (#F8F8F5) so the dynamic text has a clean
# area to render into; the original raw asset is left untouched.
#
# course_name_font_file / issue_date_font_file are intentionally left blank: no
# matched serif/sans .ttf was supplied for these two fields yet, so
# generate_certificate() falls back to Pillow's bundled default font as a
# PLACEHOLDER. Swap in a closer-matched .ttf via the calibration tool once one
# is sourced.


def seed_default_template(apps, schema_editor):
    CertificateTemplate = apps.get_model('certificates', 'CertificateTemplate')
    if CertificateTemplate.objects.filter(is_default=True).exists():
        return

    template = CertificateTemplate(
        name='Siorik Consultancy Default',
        is_default=True,
        staff_name_x_percent=50.0,
        staff_name_y_percent=47.3,
        staff_name_font_size=110,
        staff_name_color='#E9B730',
        staff_name_text_align='CENTER',
        course_name_x_percent=50.0,
        course_name_y_percent=61.8,
        course_name_font_size=34,
        course_name_color='#3A3A3A',
        course_name_text_align='CENTER',
        issue_date_x_percent=64.5,
        issue_date_y_percent=67.4,
        issue_date_font_size=28,
        issue_date_color='#3A3A3A',
        issue_date_text_align='LEFT',
        qr_code_x_percent=87.0,
        qr_code_y_percent=84.0,
        qr_code_size_percent=10.0,
    )
    # Point straight at the already-present media files rather than copying
    # them into a new upload path — these are the actual assets being seeded.
    template.background_image.name = 'certificate_templates/backgrounds/certificate_template_clean.png'
    template.staff_name_font_file.name = 'certificates/AlexBrush-Regular.ttf'
    template.save()


def unseed_default_template(apps, schema_editor):
    CertificateTemplate = apps.get_model('certificates', 'CertificateTemplate')
    CertificateTemplate.objects.filter(name='Siorik Consultancy Default', is_default=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('certificates', '0002_certificatetemplate'),
    ]

    operations = [
        migrations.RunPython(seed_default_template, unseed_default_template),
    ]
