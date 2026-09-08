"""
Parsing for the staff-enrollment bulk upload (Front-line / Officer / Middle
Management / Top Management staff → real LEARNER accounts, each tagged with the
assessment level that later drives which role-based assessment they see).

Tolerant on purpose: the file institutions actually send back is the
"LBBL_Staff_Enrollment_Template" .xlsx — multiple sheets, a title row above the
header, "Phone Number (optional)"-style header labels, assessment-level values
written as "Assistant-Supervisor" or "Front-Line Level", and ~100 pre-filled
rows where only the Organization column is populated. All of that is handled
here rather than pushed back on the uploader.
"""
import csv
import io

from openpyxl import load_workbook

from .models import User

# Normalised header cell -> field name. Normalisation lowercases, trims, drops a
# trailing "(optional)", and collapses runs of whitespace/slashes to a single space.
_HEADER_ALIASES = {
    'full name': 'name',
    'name': 'name',
    'email address': 'email',
    'email': 'email',
    'corporate title': 'corporate_title',
    'functional title': 'functional_title',
    'branch department': 'branch_department',
    'branch / department': 'branch_department',
    'assessment level': 'assessment_level',
    'phone number': 'phone_number',
    'phone': 'phone_number',
    'organization': 'organization',
    'organisation': 'organization',
}

_REQUIRED_FIELDS = {'name', 'email', 'assessment_level', 'organization'}

# Every spelling we accept for each of the four stored codes — the codes
# themselves, the current display labels, and the older ones from the template.
_LEVEL_ALIASES = {
    'assistant_supervisor': User.AssessmentLevel.ASSISTANT_SUPERVISOR,
    'assistant-supervisor': User.AssessmentLevel.ASSISTANT_SUPERVISOR,
    'assistant/supervisor': User.AssessmentLevel.ASSISTANT_SUPERVISOR,
    'assistant supervisor': User.AssessmentLevel.ASSISTANT_SUPERVISOR,
    'front-line level': User.AssessmentLevel.ASSISTANT_SUPERVISOR,
    'front line level': User.AssessmentLevel.ASSISTANT_SUPERVISOR,
    'frontline level': User.AssessmentLevel.ASSISTANT_SUPERVISOR,
    'front-line': User.AssessmentLevel.ASSISTANT_SUPERVISOR,
    'officer': User.AssessmentLevel.OFFICER,
    'officer level': User.AssessmentLevel.OFFICER,
    'management': User.AssessmentLevel.MANAGEMENT,
    'middle management level': User.AssessmentLevel.MANAGEMENT,
    'middle management': User.AssessmentLevel.MANAGEMENT,
    'senior_management': User.AssessmentLevel.SENIOR_MANAGEMENT,
    'senior management': User.AssessmentLevel.SENIOR_MANAGEMENT,
    'top management level': User.AssessmentLevel.SENIOR_MANAGEMENT,
    'top management': User.AssessmentLevel.SENIOR_MANAGEMENT,
}

# Shown in the "invalid level" failure reason and the frontend help text.
ACCEPTED_LEVEL_LABELS = ['Front-Line Level', 'Officer Level', 'Middle Management Level', 'Top Management Level']

_MAX_HEADER_SCAN_ROWS = 15


class StaffImportError(Exception):
    """Whole-file failure — the upload can't be read at all, or no header row
    was found in any sheet. There's no single row to attribute it to."""


def _cell(value):
    return '' if value is None else str(value).strip()


def _normalise_header(text):
    text = _cell(text).lower()
    if text.endswith(')') and '(' in text:
        text = text[: text.rindex('(')].strip()
    return ' '.join(text.replace('/', ' ').split())


def resolve_assessment_level(raw):
    """The stored code for a free-text level cell, or None if unrecognised."""
    key = ' '.join(_cell(raw).lower().split())
    return _LEVEL_ALIASES.get(key)


def _column_map(header_row):
    """field name -> column index for a candidate header row, or None if it
    doesn't carry every required column."""
    index_by_field = {}
    for index, cell in enumerate(header_row):
        field = _HEADER_ALIASES.get(_normalise_header(cell))
        if field and field not in index_by_field:
            index_by_field[field] = index
    return index_by_field if _REQUIRED_FIELDS <= set(index_by_field) else None


def _iter_sheet_rows(upload, filename):
    """Yield row tuples from the upload — the first sheet of an .xlsx, or a
    decoded .csv. Raises StaffImportError if neither works."""
    name = (filename or '').lower()
    if name.endswith('.csv'):
        try:
            decoded = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise StaffImportError('Could not read the uploaded .csv as UTF-8 text.') from exc
        yield from csv.reader(io.StringIO(decoded))
        return

    try:
        workbook = load_workbook(upload, data_only=True, read_only=True)
    except Exception as exc:
        raise StaffImportError(f'Could not read the uploaded file as an .xlsx workbook: {exc}') from exc

    # Use the first sheet that has a recognisable header row (the template's
    # data lives on "Staff Details", after an "Instructions" sheet).
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if any(_column_map(row or ()) for row in rows[:_MAX_HEADER_SCAN_ROWS]):
            yield from rows
            return
    yield from []


def parse_staff_rows(upload, filename):
    """
    Returns (rows, failures):
      rows     -- list of dicts {name, email, organization_name, corporate_title,
                  functional_title, branch_department, phone_number,
                  assessment_level} for every valid staff row.
      failures -- list of {row, email, reason} for every rejected row.

    Raises StaffImportError only for a whole-file problem (unreadable upload, or
    no header row anywhere in it).
    """
    all_rows = list(_iter_sheet_rows(upload, filename))

    header_index = next(
        (i for i, row in enumerate(all_rows[:_MAX_HEADER_SCAN_ROWS]) if _column_map(row or ())),
        None,
    )
    if header_index is None:
        raise StaffImportError(
            'No header row found. The sheet needs a row with at least these columns: '
            'Full Name, Email Address, Assessment Level, Organization.'
        )

    columns = _column_map(all_rows[header_index])

    def col(row, field):
        index = columns.get(field)
        if index is None or index >= len(row):
            return ''  # an optional column (corporate title, phone, ...) the file omitted
        return _cell(row[index])

    rows = []
    failures = []
    seen_emails = set()

    for offset, raw_row in enumerate(all_rows[header_index + 1 :], start=header_index + 2):
        row = raw_row or ()
        name = col(row, 'name')
        email = col(row, 'email')

        # A row is a data row only if it names a person. The template ships with
        # ~100 rows where only Organization is pre-filled — those are not errors.
        if not name and not email:
            continue

        if not name or not email:
            failures.append({'row': offset, 'email': email, 'reason': 'Both Full Name and Email Address are required.'})
            continue

        email_key = email.lower()
        if email_key in seen_emails:
            failures.append({'row': offset, 'email': email, 'reason': 'Duplicate email within this file.'})
            continue
        seen_emails.add(email_key)

        org_name = col(row, 'organization')
        if not org_name:
            failures.append({'row': offset, 'email': email, 'reason': 'Organization is required.'})
            continue

        level_raw = col(row, 'assessment_level')
        assessment_level = resolve_assessment_level(level_raw)
        if assessment_level is None:
            failures.append({
                'row': offset,
                'email': email,
                'reason': f'Assessment Level "{level_raw}" must be one of: ' + ', '.join(ACCEPTED_LEVEL_LABELS) + '.',
            })
            continue

        rows.append({
            'name': name,
            'email': email,
            'organization_name': org_name,
            'corporate_title': col(row, 'corporate_title'),
            'functional_title': col(row, 'functional_title'),
            'branch_department': col(row, 'branch_department'),
            'phone_number': col(row, 'phone_number'),
            'assessment_level': str(assessment_level),
        })

    return rows, failures
