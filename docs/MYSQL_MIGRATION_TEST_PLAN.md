# Periodic Exam migration test plan for a production MySQL copy

Run this only against a disposable copy of production. Never point Django or a destructive command at the production database. The Periodic Exam migration is additive: `periodic_exams.0001_initial` creates two new tables and does not alter existing tables.

## 1. Prepare names and take a production backup

Use a unique test database name and a backup path outside the repository. Do not put a database password on the command line; let `mysqldump`/`mysql` prompt for it.

```bash
export MYSQL_HOST='production-mysql-host'
export MYSQL_USER='production-readonly-backup-user'
export SOURCE_DB='production_database_name'
export TEST_DB='siorik_periodic_exam_migration_YYYYMMDD'
export BACKUP_FILE="/secure/backups/${SOURCE_DB}-periodic-exam-YYYYMMDD.sql"

mysqldump --host="$MYSQL_HOST" --user="$MYSQL_USER" --password \
  --single-transaction --quick --routines --triggers --events \
  --default-character-set=utf8mb4 "$SOURCE_DB" > "$BACKUP_FILE"
sha256sum "$BACKUP_FILE" > "${BACKUP_FILE}.sha256"
sha256sum --check "${BACKUP_FILE}.sha256"
```

Record the production row counts before restoration:

```bash
mysql --host="$MYSQL_HOST" --user="$MYSQL_USER" --password --database="$SOURCE_DB" --batch --skip-column-names \
  -e "SELECT 'organizations',COUNT(*) FROM accounts_organization UNION ALL SELECT 'users',COUNT(*) FROM accounts_user UNION ALL SELECT 'migrations',COUNT(*) FROM django_migrations;"
```

## 2. Create and restore the disposable test database

Use a MySQL account authorised only for the test database. Verify the resolved database name before continuing. Drop/recreate only the explicitly named test database, never the source database.

```bash
export TEST_MYSQL_HOST='test-mysql-host'
export TEST_MYSQL_ADMIN='test-database-admin'

printf 'Source: %s\nTest target: %s on %s\n' "$SOURCE_DB" "$TEST_DB" "$TEST_MYSQL_HOST"
mysql --host="$TEST_MYSQL_HOST" --user="$TEST_MYSQL_ADMIN" --password \
  -e "CREATE DATABASE \`$TEST_DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql --host="$TEST_MYSQL_HOST" --user="$TEST_MYSQL_ADMIN" --password \
  --default-character-set=utf8mb4 "$TEST_DB" < "$BACKUP_FILE"
```

Confirm the copy, server version, charset and baseline counts:

```bash
mysql --host="$TEST_MYSQL_HOST" --user="$TEST_MYSQL_ADMIN" --password --database="$TEST_DB" \
  -e "SELECT DATABASE(),VERSION(),@@character_set_database,@@collation_database; SELECT 'organizations',COUNT(*) FROM accounts_organization UNION ALL SELECT 'users',COUNT(*) FROM accounts_user UNION ALL SELECT 'migrations',COUNT(*) FROM django_migrations;"
```

The three counts must match the production values recorded above before any migration is run.

## 3. Point an isolated checkout at the copy

Create an uncommitted `backend/.env.mysql-periodic-copy` from the normal environment file and set only the test connection values. Keep it outside Git and restrict its filesystem permissions.

```dotenv
DB_ENGINE=mysql
DB_HOST=test-mysql-host
DB_PORT=3306
DB_NAME=siorik_periodic_exam_migration_YYYYMMDD
DB_USER=test_database_user
DB_PASSWORD=use-a-secret-value-not-committed-to-git
```

Load that file in the shell, then confirm Django is using MySQL and the exact disposable database before migration:

```bash
cd /path/to/feature-periodic-exam-v2/backend
set -a
. ./.env.mysql-periodic-copy
set +a
python manage.py shell -c "from django.db import connection; print(connection.vendor, connection.settings_dict['HOST'], connection.settings_dict['NAME'])"
python manage.py check
python manage.py showmigrations periodic_exams
python manage.py migrate periodic_exams 0001 --plan
```

Stop if the printed vendor is not `mysql`, the host is production, or the database name is not the unique test name.

## 4. Apply and verify the migration

```bash
python manage.py migrate periodic_exams 0001 --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py showmigrations periodic_exams
```

Check migration recording, tables, engine, charset, columns, constraints and indexes:

```bash
mysql --host="$TEST_MYSQL_HOST" --user="$TEST_MYSQL_ADMIN" --password --database="$TEST_DB" <<'SQL'
SELECT app,name,applied FROM django_migrations WHERE app='periodic_exams' ORDER BY name;
SELECT TABLE_NAME,ENGINE,TABLE_COLLATION
FROM information_schema.TABLES
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('periodic_exams_periodicexamsettings','periodic_exams_periodicexamcycle');
SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,CHARACTER_SET_NAME,COLLATION_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('periodic_exams_periodicexamsettings','periodic_exams_periodicexamcycle')
ORDER BY TABLE_NAME,ORDINAL_POSITION;
SHOW CREATE TABLE periodic_exams_periodicexamsettings;
SHOW CREATE TABLE periodic_exams_periodicexamcycle;
SHOW INDEX FROM periodic_exams_periodicexamsettings;
SHOW INDEX FROM periodic_exams_periodicexamcycle;
SELECT CONSTRAINT_NAME,CONSTRAINT_TYPE,TABLE_NAME
FROM information_schema.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'periodic_exams_%'
ORDER BY TABLE_NAME,CONSTRAINT_NAME;
SELECT COUNT(*) AS settings_rows FROM periodic_exams_periodicexamsettings;
SELECT COUNT(*) AS cycle_rows FROM periodic_exams_periodicexamcycle;
SQL
```

Expected checks:

- Both tables use InnoDB and `utf8mb4` collation; every textual column is `utf8mb4`.
- `pe_cycle_current_idx`, `pe_cycle_recent_idx`, `pe_cycle_org_sequence_unique` and `pe_cycle_org_start_unique` exist.
- Index columns are numeric IDs/dates/datetimes, not long text. `SHOW INDEX` must show no unexpected prefix truncation (`Sub_part` should be `NULL`); estimated key size must remain below the InnoDB 3072-byte limit for the server/row format.
- Foreign keys target `accounts_organization` and the configured user table. Check constraints should appear where supported by the deployed MySQL version.
- New tables should initially contain zero rows because `0001` has no data migration.
- The previously recorded organization, user and migration counts remain unchanged except that `django_migrations` gains one `periodic_exams` row.

Exercise the settings API or Django shell on the copy to create one settings row and one cycle, then confirm timestamps, JSON reminder days, uniqueness constraints and tenant foreign keys round-trip correctly. Remove only these disposable test rows before the reverse test.

## 5. Reverse and reapply on the copy

Review the destructive reverse plan, verify the database target again, then reverse only the Periodic Exam app:

```bash
python manage.py shell -c "from django.db import connection; print(connection.vendor, connection.settings_dict['HOST'], connection.settings_dict['NAME'])"
python manage.py migrate periodic_exams zero --plan
python manage.py migrate periodic_exams zero --noinput
python manage.py showmigrations periodic_exams
```

Verify both Periodic Exam tables are gone, the `periodic_exams` migration row is gone, and all pre-existing row counts are unchanged:

```bash
mysql --host="$TEST_MYSQL_HOST" --user="$TEST_MYSQL_ADMIN" --password --database="$TEST_DB" \
  -e "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'periodic_exams_%'; SELECT COUNT(*) FROM django_migrations WHERE app='periodic_exams'; SELECT 'organizations',COUNT(*) FROM accounts_organization UNION ALL SELECT 'users',COUNT(*) FROM accounts_user;"
```

Reapply once more and repeat the checks from section 4 to prove forward/reverse/forward consistency:

```bash
python manage.py migrate periodic_exams 0001 --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

## 6. Finish safely

Save command output, MySQL version, timings, row-count comparisons and `SHOW CREATE TABLE` results with the review record. Remove the temporary environment file securely. After review, drop only the uniquely named disposable test database using the test host/admin account; retain the encrypted backup under the organisation's backup policy.
