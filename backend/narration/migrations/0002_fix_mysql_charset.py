from django.db import migrations

# MySQL/MariaDB created this table under the database's default charset
# (latin1 on this host), even though the connection itself is utf8mb4 (see
# core/settings.py) — Django's OPTIONS={'charset': 'utf8mb4'} only governs
# how bytes travel over the connection, not what charset a CREATE TABLE
# inherits. Devanagari script_text (or any non-Latin1 text) written through
# a latin1 column gets silently mangled into literal '?' characters at
# INSERT time — this is data corruption, not a display/font issue, and
# isn't reversible by fixing the charset after the fact; any row written
# before this migration needs to be regenerated. No-op on PostgreSQL (local
# dev), which has no such column-level charset concept — every table there
# is UTF-8 already.
def convert_to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'ALTER TABLE narration_slidenarration CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('narration', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(convert_to_utf8mb4, noop),
    ]
