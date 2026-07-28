from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0008_migrate_page_content_to_slides'),
        ('assessments', '0006_finalize_quiz_slide'),
        ('assignments', '0003_finalize_assignment_slide'),
    ]

    operations = [
        # Children first, so their FKs to Page are gone before Page itself.
        migrations.DeleteModel(name='PageRevision'),
        migrations.DeleteModel(name='PageProgress'),
        migrations.DeleteModel(name='Page'),
    ]
