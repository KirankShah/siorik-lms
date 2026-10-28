import csv
import io
from dataclasses import asdict, dataclass

from django.db.models import Count, F, Max, Q
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from openpyxl import Workbook

from accounts.models import User
from .models import PeriodicExamParticipant


BASE_REPORT_HEADERS = [
    'Staff name', 'Email', 'Level', 'Branch/department', 'Exam month', 'Attempted',
    'Completed', 'Attempts used', 'Best score', 'Status', 'Last attempt date',
]
LEVEL_LABELS = dict(User.AssessmentLevel.choices)


@dataclass(frozen=True)
class PeriodicExamReportRow:
    staff_name: str
    email: str
    level: str
    branch_department: str
    cycle: str
    attempted: bool
    completed: bool
    attempts_used: int
    best_score: float | None
    status: str
    last_attempt_date: str | None
    attempt_scores: list[float | None]

    def json(self):
        return asdict(self)

    def cells(self, max_attempts):
        values = [
            self.staff_name, self.email, self.level, self.branch_department, self.cycle,
            self.attempted, self.completed, self.attempts_used, self.best_score,
            self.status, self.last_attempt_date,
        ]
        return values + self.attempt_scores + [None] * (max_attempts - len(self.attempt_scores))


def report_headers(max_attempts):
    return BASE_REPORT_HEADERS + [f'Attempt {number} score' for number in range(1, max_attempts + 1)]


def report_participants(cycle, *, search='', status_filter=''):
    return _filter_report_participants(cycle.participants.all(), search=search, status_filter=status_filter)


def report_participants_for_organization(organization, *, search='', status_filter=''):
    queryset = PeriodicExamParticipant.objects.filter(cycle__organization=organization)
    return _filter_report_participants(queryset, search=search, status_filter=status_filter)


def _filter_report_participants(queryset, *, search='', status_filter=''):
    queryset = queryset.annotate(
        report_attempt_count=Count('attempts', distinct=True),
        report_completed_count=Count(
            'attempts', filter=Q(attempts__submitted_at__isnull=False), distinct=True
        ),
        report_open_count=Count(
            'attempts', filter=Q(attempts__submitted_at__isnull=True), distinct=True
        ),
        report_last_attempt_at=Max('attempts__started_at'),
    )
    if search:
        queryset = queryset.filter(
            Q(name_snapshot__icontains=search)
            | Q(email_snapshot__icontains=search)
            | Q(level_snapshot__icontains=search)
            | Q(branch_department_snapshot__icontains=search)
        )
    status_filters = {
        'Passed': Q(passed_at__isnull=False),
        'Not attempted': Q(report_attempt_count=0),
        'In progress': Q(passed_at__isnull=True, report_open_count__gt=0),
        'Failed': Q(
            passed_at__isnull=True,
            report_completed_count__gte=F('cycle__max_attempts_per_cycle'),
            report_open_count=0,
        ),
        'Retake required': Q(
            passed_at__isnull=True,
            report_completed_count__gt=0,
            report_completed_count__lt=F('cycle__max_attempts_per_cycle'),
            report_open_count=0,
        ),
    }
    if status_filter in status_filters:
        queryset = queryset.filter(status_filters[status_filter])
    return queryset.order_by('name_snapshot', 'email_snapshot', 'learner_id_snapshot')


def build_report_row(participant):
    attempts = participant.report_attempt_count
    attempt_rows = sorted(participant.attempts.all(), key=lambda attempt: attempt.attempt_number)
    if participant.passed_at:
        status = 'Passed'
    elif attempts == 0:
        status = 'Not attempted'
    elif participant.report_open_count:
        status = 'In progress'
    elif participant.report_completed_count >= participant.cycle.max_attempts_per_cycle:
        status = 'Failed'
    else:
        status = 'Retake required'
    completed = status in ('Passed', 'Failed')
    last_attempt = participant.report_last_attempt_at
    if last_attempt:
        last_attempt = timezone.localtime(last_attempt).isoformat()
    return PeriodicExamReportRow(
        staff_name=participant.name_snapshot or participant.email_snapshot,
        email=participant.email_snapshot,
        level=LEVEL_LABELS.get(participant.level_snapshot, participant.level_snapshot),
        branch_department=participant.branch_department_snapshot,
        cycle=participant.cycle.display_label,
        attempted=attempts > 0,
        completed=completed,
        attempts_used=attempts,
        best_score=float(participant.best_score_percent) if participant.best_score_percent is not None else None,
        status=status,
        last_attempt_date=last_attempt,
        attempt_scores=[
            float(attempt.score_percent) if attempt.submitted_at is not None else None
            for attempt in attempt_rows
        ],
    )


def iter_report_rows(queryset, *, chunk_size=500):
    for participant in queryset.select_related('cycle').prefetch_related('attempts').iterator(chunk_size=chunk_size):
        yield build_report_row(participant)


FORMULA_TRIGGERS = ('=', '+', '-', '@', '\t', '\r', '\n')


def spreadsheet_safe(value):
    if isinstance(value, str) and value.startswith(FORMULA_TRIGGERS):
        return "'" + value
    return value


class _CsvEcho:
    def write(self, value):
        return value


def csv_report_response(queryset, cycle):
    writer = csv.writer(_CsvEcho())
    max_attempts = cycle.max_attempts_per_cycle if cycle else (
        queryset.aggregate(value=Max('cycle__max_attempts_per_cycle'))['value'] or 0
    )

    def content():
        yield '\ufeff'
        yield writer.writerow(report_headers(max_attempts))
        for row in iter_report_rows(queryset):
            yield writer.writerow([spreadsheet_safe(value) for value in row.cells(max_attempts)])

    response = StreamingHttpResponse(content(), content_type='text/csv; charset=utf-8')
    suffix = cycle.id if cycle else 'history'
    response['Content-Disposition'] = f'attachment; filename="periodic_exam_{suffix}.csv"'
    return response


def xlsx_report_response(queryset, cycle):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet('Periodic Exam Report')
    max_attempts = cycle.max_attempts_per_cycle if cycle else (
        queryset.aggregate(value=Max('cycle__max_attempts_per_cycle'))['value'] or 0
    )
    sheet.append(report_headers(max_attempts))
    for row in iter_report_rows(queryset):
        sheet.append([spreadsheet_safe(value) for value in row.cells(max_attempts)])
    buffer = io.BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    suffix = cycle.id if cycle else 'history'
    response['Content-Disposition'] = f'attachment; filename="periodic_exam_{suffix}.xlsx"'
    return response
