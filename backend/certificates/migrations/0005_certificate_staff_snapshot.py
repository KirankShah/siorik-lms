from django.db import migrations, models
import django.db.models.deletion


def snapshot_staff_details(apps, schema_editor):
    Certificate = apps.get_model('certificates', 'Certificate')
    User = apps.get_model('accounts', 'User')
    level_labels = dict(User._meta.get_field('assessment_level').choices)
    batch = []
    for certificate in Certificate.objects.select_related('user').iterator(chunk_size=500):
        user = certificate.user
        if user is None:
            continue
        certificate.staff_name = (
            ' '.join(part for part in [user.first_name, user.last_name] if part).strip() or user.email
        )
        certificate.staff_email = user.email
        certificate.staff_level = level_labels.get(user.assessment_level, '')
        certificate.staff_organization_id = user.organization_id
        batch.append(certificate)
        if len(batch) == 500:
            Certificate.objects.bulk_update(
                batch, ['staff_name', 'staff_email', 'staff_level', 'staff_organization_id'], batch_size=500,
            )
            batch.clear()
    if batch:
        Certificate.objects.bulk_update(
            batch, ['staff_name', 'staff_email', 'staff_level', 'staff_organization_id'], batch_size=500,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0010_staffinvitationjob_staffinvitation'),
        ('certificates', '0004_certificatetemplate_organization_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificate',
            name='staff_name',
            field=models.CharField(blank=True, max_length=320),
        ),
        migrations.AddField(
            model_name='certificate',
            name='staff_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='certificate',
            name='staff_level',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='certificate',
            name='staff_organization_id',
            field=models.PositiveBigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(snapshot_staff_details, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='certificate',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificates', to='accounts.user'),
        ),
    ]
