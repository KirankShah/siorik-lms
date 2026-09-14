from django.db import migrations

# Same fix as narration.migrations.0002_fix_mysql_charset: MySQL/MariaDB
# creates a table under the database's default charset (latin1 on
# production), even though the connection itself is utf8mb4 — Django's
# OPTIONS={'charset': 'utf8mb4'} only governs bytes on the wire, not what
# charset a CREATE TABLE inherits. A Nepali resource title/description
# written through a latin1 column gets silently corrupted at INSERT time.
# No-op on PostgreSQL (local dev), which has no column-level charset concept.
def convert_to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'ALTER TABLE resources_resource CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(convert_to_utf8mb4, noop),
    ]
