from django.db import migrations

# Mirrors the seed data in 0002_seed_badges.py / 0007_seed_level_assessment_badges.py
# / 0009_seed_tier_and_streak_badges.py — re-applied here as plain UPDATEs
# (not get_or_create) since those rows already exist with a corrupted icon.
BADGE_ICONS = {
    'first_course_complete': '🎓',
    'five_courses_complete': '🏆',
    'perfect_score': '💯',
    'high_achiever': '⭐',
    'first_strike': '🎯',
    'hat_trick': '🎩',
    'comeback': '🔥',
    'branch_pride': '🏅',
    'tier_complete_foundation': '🏁',
    'tier_complete_assistant_supervisor': '🎖️',
    'tier_complete_officer': '🎖️',
    'tier_complete_management': '🎖️',
    'tier_complete_senior_management': '🎖️',
    'streak_3_day': '🔥',
}


def convert_mysql_charset_to_utf8mb4(apps, schema_editor):
    """
    One-time fix for a database (and every table in it) provisioned with
    MySQL/MariaDB's legacy latin1 default charset instead of utf8mb4 — the
    root cause behind achievement badge icons rendering as '?'/'??'.
    latin1 can't represent 4-byte-in-UTF-8 characters (most emoji) or, more
    seriously, ANY character outside Latin-1's own 256-code range
    (Devanagari narration transcripts, curly quotes/em-dashes from rich
    text, etc.) — MySQL silently replaces anything it can't transcode with
    a literal '?' in non-strict mode, which is unrecoverable once written.
    core/settings.py's connection OPTIONS={'charset': 'utf8mb4'} only
    controls the CLIENT<->SERVER session encoding — it does nothing for
    data already sitting in latin1-charset columns, or for how new tables
    get created, since MySQL's CREATE TABLE inherits the DATABASE's own
    default charset when a table doesn't specify one, and Django's mysql
    backend doesn't override that per table.

    No-op on every other backend (Postgres stores text as UTF-8 natively
    and has no equivalent "table charset" concept — local dev and the test
    suite both run Postgres, so this is a no-op there).

    CONVERT TO CHARACTER SET is lossless for existing data: latin1's 256
    code points map 1:1 onto Unicode's first 256 code points, so this just
    re-encodes what's already stored (pure ASCII content converts byte-for-
    byte identically) — it does not, and cannot, recover any character a
    prior write already replaced with a literal '?'. That's what the
    follow-up reseed_badge_icons below is for, for the one place we know
    exactly what the original value should have been.
    """
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        db_name = schema_editor.connection.settings_dict['NAME']
        try:
            cursor.execute(f'ALTER DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        except Exception as exc:  # noqa: BLE001 — only affects future tables; don't block fixing existing ones below
            print(f'  Could not convert the database default charset (continuing anyway): {exc}')

        cursor.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_COLLATION NOT LIKE 'utf8mb4%%'",
            [db_name],
        )
        table_names = [row[0] for row in cursor.fetchall()]
        converted, failed = [], []
        for table_name in table_names:
            try:
                cursor.execute(
                    f'ALTER TABLE `{table_name}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
                )
                converted.append(table_name)
            except Exception as exc:  # noqa: BLE001 — one bad table shouldn't block the rest
                failed.append((table_name, str(exc)))
        print(f'  Converted {len(converted)} table(s) to utf8mb4.')
        if failed:
            print(f'  FAILED to convert {len(failed)} table(s): {failed}')


def reseed_badge_icons(apps, schema_editor):
    """Re-applies every badge's intended icon now that the schema can
    actually store it."""
    Badge = apps.get_model('gamification', 'Badge')
    for key, icon in BADGE_ICONS.items():
        Badge.objects.filter(key=key).update(icon=icon)


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0009_seed_tier_and_streak_badges'),
    ]

    operations = [
        # Reversing either of these would mean re-corrupting data or
        # discarding the recovered icons — neither is a sensible "undo", so
        # both are one-directional (noop reverse) rather than truly
        # reversible.
        migrations.RunPython(convert_mysql_charset_to_utf8mb4, migrations.RunPython.noop),
        migrations.RunPython(reseed_badge_icons, migrations.RunPython.noop),
    ]
