"""
Admin-only bulk import of LevelQuestion/LevelChoice records from the "Level
Assessment Question Template" spreadsheet, for a specific AssessmentLevel.
Reporting follows the same pattern as accounts.views.DemoUserViewSet.bulk's
CSV upload: each row is validated and, if valid, committed immediately;
invalid rows are never silently dropped — they're collected with a reason
and reported back alongside whatever did succeed.
"""
from django.db import transaction
from openpyxl import load_workbook

from .models import LevelAssessmentAnswer, LevelChoice, LevelQuestion, QuestionSet

OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E']
REQUIRED_OPTION_LETTERS = ['A', 'B', 'C', 'D']

# Normalized (lowercased, trimmed) header cell -> internal field name. Column
# order in the uploaded sheet doesn't matter, only that every one of these is
# present somewhere in the header row.
TEMPLATE_COLUMNS = {
    'question set': 'question_set',
    'question text': 'question_text',
    'question type': 'question_type',
    'option a': 'option_a',
    'option b': 'option_b',
    'option c': 'option_c',
    'option d': 'option_d',
    'option e': 'option_e',
    'correct answer(s)': 'correct_answers',
    'marks': 'marks',
    'explanation': 'explanation',
    'feedback if correct': 'feedback_correct',
    'feedback if incorrect': 'feedback_incorrect',
}

QUESTION_TYPE_LABELS = {
    'single choice': LevelQuestion.QuestionType.SINGLE_CHOICE,
    'multiple answer': LevelQuestion.QuestionType.MULTIPLE_ANSWER,
}


class LevelQuestionImportError(Exception):
    """Raised only for a whole-file failure (the upload can't be read as an
    .xlsx workbook at all) — there's no single row to blame, so this isn't
    reported through the per-row failure list."""


def _cell_text(value):
    return '' if value is None else str(value).strip()


def _column_index_map(header_row):
    """Maps internal field name -> column index from a header row. Raises
    ValueError (caller turns this into one per-sheet failure entry, not a
    whole-file error) listing whichever required column headers are absent."""
    index_by_field = {}
    for index, cell in enumerate(header_row):
        field = TEMPLATE_COLUMNS.get(_cell_text(cell).lower())
        if field:
            index_by_field[field] = index

    missing_fields = set(TEMPLATE_COLUMNS.values()) - set(index_by_field)
    if missing_fields:
        missing_labels = sorted(label for label, field in TEMPLATE_COLUMNS.items() if field in missing_fields)
        raise ValueError(f'Missing required column(s): {", ".join(missing_labels)}.')
    return index_by_field


def parse_correct_answers(raw, question_type):
    """
    Public so the Question Bank admin edit form (levelassessments.serializers.
    LevelQuestionEditSerializer) can validate an edit against the exact same
    rules as an Excel import row, rather than a separately-maintained copy
    that could silently drift from these.
    """
    letters = [part.strip().upper() for part in raw.split(',') if part.strip()]
    if not letters:
        return None, 'Correct Answer(s) is required.'
    invalid_letters = [letter for letter in letters if letter not in OPTION_LETTERS]
    if invalid_letters:
        return None, f'Correct Answer(s) "{raw}" must reference option letters A-E only.'
    if len(set(letters)) != len(letters):
        return None, f'Correct Answer(s) "{raw}" lists the same option more than once.'
    if question_type == LevelQuestion.QuestionType.SINGLE_CHOICE and len(letters) != 1:
        return None, 'Single Choice questions must have exactly one Correct Answer.'
    return letters, None


def parse_marks(raw):
    """Public — see parse_correct_answers."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, f'Marks "{raw}" is not a number.'
    if value <= 0 or value != int(value):
        return None, f'Marks "{raw}" must be a positive whole number.'
    return int(value), None


def validate_options(options, correct_letters):
    """
    Public — same reuse reason as parse_correct_answers. `options` is a dict
    keyed by OPTION_LETTERS; A-D must be filled (E is optional), and every
    letter in `correct_letters` must reference a filled option. Returns an
    error message, or None if valid.
    """
    missing_required = [letter for letter in REQUIRED_OPTION_LETTERS if not options.get(letter)]
    if missing_required:
        return f'Option {", ".join(missing_required)} must be filled in.'
    missing_referenced = [letter for letter in correct_letters if not options.get(letter)]
    if missing_referenced:
        return f'Correct Answer(s) references empty option(s): {", ".join(missing_referenced)}.'
    return None


def _parse_row(row, column_index):
    def col(field):
        index = column_index[field]
        return _cell_text(row[index]) if index < len(row) else ''

    question_set_label = col('question_set')
    question_text = col('question_text')
    question_type_raw = col('question_type')
    options = {letter: col(f'option_{letter.lower()}') for letter in OPTION_LETTERS}
    correct_answers_raw = col('correct_answers')
    marks_raw = col('marks')

    if not question_set_label:
        return None, 'Missing Question Set.'
    if not question_text:
        return None, 'Missing Question Text.'

    question_type = QUESTION_TYPE_LABELS.get(question_type_raw.lower())
    if question_type is None:
        return None, f'Question Type "{question_type_raw}" must be "Single Choice" or "Multiple Answer".'

    letters, error = parse_correct_answers(correct_answers_raw, question_type)
    if error:
        return None, error

    options_error = validate_options(options, letters)
    if options_error:
        return None, options_error

    marks, error = parse_marks(marks_raw)
    if error:
        return None, error

    return {
        'question_set_label': question_set_label,
        'question_text': question_text,
        'question_type': question_type,
        'options': options,
        'correct_letters': letters,
        'marks': marks,
        'explanation': col('explanation'),
        'feedback_correct': col('feedback_correct'),
        'feedback_incorrect': col('feedback_incorrect'),
    }, None


def _create_question(assessment_level, parsed):
    question_set, _ = QuestionSet.objects.get_or_create(
        assessment_level=assessment_level, label=parsed['question_set_label']
    )
    question = LevelQuestion.objects.create(
        question_set=question_set,
        question_text=parsed['question_text'],
        question_type=parsed['question_type'],
        marks=parsed['marks'],
        explanation=parsed['explanation'],
        feedback_correct=parsed['feedback_correct'],
        feedback_incorrect=parsed['feedback_incorrect'],
    )
    for order, letter in enumerate(OPTION_LETTERS):
        option_text = parsed['options'][letter]
        if not option_text:
            continue
        LevelChoice.objects.create(
            question=question,
            choice_text=option_text,
            is_correct=letter in parsed['correct_letters'],
            order=order,
        )
    return question, question_set


def _load_workbook(workbook_file):
    try:
        return load_workbook(workbook_file, data_only=True, read_only=True)
    except Exception as exc:
        raise LevelQuestionImportError(f'Could not read the uploaded file as an .xlsx workbook: {exc}') from exc


def _question_set_labels_in_workbook(workbook):
    """Every non-blank "Question Set" column value across every sheet's data
    rows, regardless of whether the rest of the row validates — this is what
    scopes a replace-import to only the sets the uploaded file actually
    touches, leaving every other Question Set under the level untouched."""
    labels = set()
    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        try:
            header_row = next(rows)
        except StopIteration:
            continue  # empty sheet

        try:
            column_index = _column_index_map(header_row)
        except ValueError:
            continue  # reported separately by the real import pass

        qs_index = column_index['question_set']
        for row in rows:
            if row is None:
                continue
            label = _cell_text(row[qs_index]) if qs_index < len(row) else ''
            if label:
                labels.add(label)

    return labels


def preview_replace_impact(*, assessment_level, workbook_file):
    """
    Dry-run for a replace-import: parses the workbook only far enough to find
    which existing Question Set labels (under `assessment_level`) it would
    touch, then reports how many LevelQuestion/LevelAssessmentAnswer rows a
    replace would delete — so the frontend can show a specific warning before
    the destructive import actually runs. Read-only; makes no changes.
    """
    workbook = _load_workbook(workbook_file)
    labels = _question_set_labels_in_workbook(workbook)

    matched_sets = QuestionSet.objects.filter(assessment_level=assessment_level, label__in=labels)
    matched_questions = LevelQuestion.objects.filter(question_set__in=matched_sets)

    return {
        'question_set_labels': sorted(labels),
        'existing_question_count': matched_questions.count(),
        'affected_answer_count': LevelAssessmentAnswer.objects.filter(question__in=matched_questions).count(),
    }


def import_level_questions(*, assessment_level, workbook_file, replace=False):
    """
    Parses every sheet of the uploaded Level Assessment Question Template
    workbook, creating a QuestionSet (get-or-created by each row's "Question
    Set" column label, under `assessment_level`) plus LevelQuestion/
    LevelChoice rows for every row that validates.

    Each row is validated then, if valid, committed immediately — same
    pattern as accounts.views.DemoUserViewSet.bulk's CSV upload. A row that
    fails validation is skipped and reported in `failed` with its sheet name,
    row number, and reason; it never silently disappears, and it never
    blocks any other row (including other rows in the same Question Set) from
    being imported. A sheet whose header row is missing a required template
    column is reported the same way, as a single failure for that sheet, and
    the rest of the workbook is still processed.

    When `replace` is true, every existing QuestionSet under `assessment_level`
    whose label appears anywhere in the uploaded file is deleted (cascading to
    its LevelQuestion/LevelChoice/LevelAssessmentAnswer rows — see
    preview_replace_impact for sizing that impact up front) before the file's
    rows are imported fresh. Question Sets not referenced by the file are left
    alone. The delete and the import run in one transaction, so a whole-file
    read failure never leaves the level's existing questions gone with
    nothing imported to replace them.

    Raises LevelQuestionImportError only when the upload itself can't be
    read as an .xlsx workbook — there's no row or sheet to attribute that to.

    Returns (created, failed):
      created -- list of {'sheet', 'row', 'question_set'} for each row committed.
      failed  -- list of {'sheet', 'row', 'reason'} for each row (or sheet) rejected.
    """
    workbook = _load_workbook(workbook_file)

    created = []
    failed = []

    with transaction.atomic():
        if replace:
            labels = _question_set_labels_in_workbook(workbook)
            QuestionSet.objects.filter(assessment_level=assessment_level, label__in=labels).delete()

        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            try:
                header_row = next(rows)
            except StopIteration:
                continue  # empty sheet

            try:
                column_index = _column_index_map(header_row)
            except ValueError as exc:
                failed.append({'sheet': sheet.title, 'row': None, 'reason': str(exc)})
                continue

            for row_number, row in enumerate(rows, start=2):
                if row is None or not any(_cell_text(cell) for cell in row):
                    continue  # blank row

                parsed, error = _parse_row(row, column_index)
                if error:
                    failed.append({'sheet': sheet.title, 'row': row_number, 'reason': error})
                    continue

                _question, question_set = _create_question(assessment_level, parsed)
                created.append({'sheet': sheet.title, 'row': row_number, 'question_set': question_set.label})

    return created, failed
