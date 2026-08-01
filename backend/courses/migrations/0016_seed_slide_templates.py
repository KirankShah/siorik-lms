from django.db import migrations

# Curated presets — a fixed, designed set rather than a raw color picker, so
# a course's slides stay visually consistent. text_color/accent_color are
# chosen for legible contrast against background_css, including on the two
# dark themes. Classic White matches the pre-templates default look exactly.
PRESETS = [
    {
        'name': 'Classic White',
        'background_css': '#ffffff',
        'text_color': '#334155',
        'accent_color': '#032147',
        'order': 1,
    },
    {
        'name': 'Soft Navy',
        'background_css': 'linear-gradient(135deg, #eef2f7, #dde6f0)',
        'text_color': '#1e293b',
        'accent_color': '#032147',
        'order': 2,
    },
    {
        'name': 'Brand Accent',
        'background_css': 'linear-gradient(135deg, #fdf6e8, #f6e8c8)',
        'text_color': '#1e293b',
        'accent_color': '#8a5a10',
        'order': 3,
    },
    {
        'name': 'Warm Neutral',
        'background_css': 'linear-gradient(135deg, #faf6f0, #f0e6d8)',
        'text_color': '#4a4038',
        'accent_color': '#8a4d26',
        'order': 4,
    },
    {
        'name': 'Soft Teal',
        'background_css': 'linear-gradient(135deg, #e9f6f5, #d3ede9)',
        'text_color': '#1c3a38',
        'accent_color': '#0d6e64',
        'order': 5,
    },
    {
        'name': 'Deep Navy Dark',
        'background_css': 'linear-gradient(135deg, #04142b, #0a2a52)',
        'text_color': '#f1f5f9',
        'accent_color': '#e1b862',
        'order': 6,
    },
    {
        'name': 'Charcoal Dark',
        'background_css': 'linear-gradient(135deg, #1c1f24, #2a2e35)',
        'text_color': '#f4f4f5',
        'accent_color': '#e1b862',
        'order': 7,
    },
]

PRESET_NAMES = [preset['name'] for preset in PRESETS]


def seed_slide_templates(apps, schema_editor):
    SlideTemplate = apps.get_model('courses', 'SlideTemplate')
    for preset in PRESETS:
        SlideTemplate.objects.update_or_create(name=preset['name'], defaults=preset)


def remove_slide_templates(apps, schema_editor):
    SlideTemplate = apps.get_model('courses', 'SlideTemplate')
    SlideTemplate.objects.filter(name__in=PRESET_NAMES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0015_slidetemplate_course_template_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_slide_templates, remove_slide_templates),
    ]
