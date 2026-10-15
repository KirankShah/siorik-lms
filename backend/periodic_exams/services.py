import hashlib
import math
import random
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from itertools import groupby
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.utils import timezone

from accounts.models import User
from levelassessments.models import LevelQuestion
from levelassessments.services import normalize_question_text

from .calendar import first_full_period_start_on_or_after, next_full_period_start, period_for
from .models import (
    PeriodicExamAttempt,
    PeriodicExamAttemptQuestion,
    PeriodicExamCycle,
    PeriodicExamCycleQuestion,
    PeriodicExamParticipant,
    PeriodicExamQuestionUsage,
    PeriodicExamSettings,
)


SUPPORTED_QUESTION_TYPES = (
    LevelQuestion.QuestionType.SINGLE_CHOICE,
    LevelQuestion.QuestionType.MULTIPLE_ANSWER,
)
SNAPSHOT_BATCH_SIZE = 500


class PeriodicExamPoolConflictError(ValueError):
    pass


class PeriodicExamError(ValueError):
    def __init__(self, detail, *, code, status_code=400):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


def question_counts_for_organizations(organization_ids):
    """Return neutral per-level unique pool counts without changing the bank."""
    organization_ids = list(organization_ids)
    counts = {
        organization_id: {
            level: {
                'level': level,
                'level_display': label,
                'question_count': 0,
            }
            for level, label in User.AssessmentLevel.choices
        }
        for organization_id in organization_ids
    }
    unique_texts = {}
    rows = LevelQuestion.objects.filter(
        question_set__assessment_level__organization_id__in=organization_ids,
        question_type__in=SUPPORTED_QUESTION_TYPES,
    ).values_list(
        'question_set__assessment_level__organization_id',
        'question_set__assessment_level__name',
        'question_text',
        'id',
    )
    for organization_id, level, question_text, question_id in rows.iterator():
        key = normalize_question_text(question_text) or f'__question_{question_id}'
        unique_texts.setdefault((organization_id, level), set()).add(key)
    for (organization_id, level), keys in unique_texts.items():
        counts[organization_id][level]['question_count'] = len(keys)
    return {
        organization_id: list(level_counts.values())
        for organization_id, level_counts in counts.items()
    }


def get_or_create_settings(organization):
    settings, _ = PeriodicExamSettings.objects.get_or_create(organization=organization)
    return settings


def _option_key(order):
    return chr(ord('A') + order) if 0 <= order < 26 else str(order)


def _question_signature(question):
    choices = [
        {
            'key': _option_key(choice.order),
            'text': choice.choice_text,
        }
        for choice in question.choices.all()
    ]
    correct_keys = sorted(
        _option_key(choice.order) for choice in question.choices.all() if choice.is_correct
    )
    signature = (
        question.question_type,
        question.marks,
        tuple((choice['key'], choice['text']) for choice in choices),
        tuple(correct_keys),
    )
    return choices, correct_keys, signature


def _build_cycle_question_rows(cycle):
    grouped = {}
    questions = LevelQuestion.objects.filter(
        question_set__assessment_level__organization_id=cycle.organization_id,
        question_type__in=SUPPORTED_QUESTION_TYPES,
    ).select_related('question_set__assessment_level').prefetch_related('choices').order_by('id')
    for question in questions.iterator(chunk_size=SNAPSHOT_BATCH_SIZE):
        level = question.question_set.assessment_level.name
        normalized = normalize_question_text(question.question_text) or f'__question_{question.id}'
        key = (level, normalized)
        choices, correct_keys, signature = _question_signature(question)
        prior = grouped.get(key)
        if prior is not None:
            if prior['signature'] != signature:
                raise PeriodicExamPoolConflictError(
                    'Conflicting duplicate Periodic Exam questions '
                    f'{prior["source_id"]} and {question.id} for level {level!r}.'
                )
            continue
        grouped[key] = {
            'signature': signature,
            'source_id': question.id,
            'row': PeriodicExamCycleQuestion(
                cycle=cycle,
                level=level,
                source_question=question,
                source_question_id_snapshot=question.id,
                normalized_text=normalized,
                normalized_text_hash=hashlib.sha256(normalized.encode('utf-8')).hexdigest(),
                question_text=question.question_text,
                question_type=question.question_type,
                marks=question.marks,
                choices=choices,
                correct_option_keys=correct_keys,
            ),
        }
    return [entry['row'] for entry in grouped.values()]


def _build_participant_rows(cycle, pool_counts, eligible_at):
    learners = User.objects.filter(
        organization_id=cycle.organization_id,
        is_active=True,
        role=User.Role.LEARNER,
        is_demo=False,
        assessment_level__isnull=False,
        date_joined__lt=cycle.starts_at,
    ).exclude(assessment_level='').order_by('id').values(
        'id', 'first_name', 'last_name', 'email', 'assessment_level', 'branch_department'
    )
    rows = []
    for learner in learners.iterator(chunk_size=SNAPSHOT_BATCH_SIZE):
        name = f'{learner["first_name"]} {learner["last_name"]}'.strip()
        rows.append(PeriodicExamParticipant(
            cycle=cycle,
            learner_id=learner['id'],
            learner_id_snapshot=learner['id'],
            name_snapshot=name,
            email_snapshot=learner['email'],
            level_snapshot=learner['assessment_level'],
            branch_department_snapshot=learner['branch_department'] or '',
            can_form_full_exam=(pool_counts.get(learner['assessment_level'], 0) >= cycle.questions_per_exam),
            eligible_at=eligible_at,
        ))
    return rows


def _materialize_cycle(cycle, eligible_at):
    question_rows = _build_cycle_question_rows(cycle)
    pool_counts = {}
    for row in question_rows:
        pool_counts[row.level] = pool_counts.get(row.level, 0) + 1
    PeriodicExamCycleQuestion.objects.bulk_create(question_rows, batch_size=SNAPSHOT_BATCH_SIZE)
    PeriodicExamParticipant.objects.bulk_create(
        _build_participant_rows(cycle, pool_counts, eligible_at),
        batch_size=SNAPSHOT_BATCH_SIZE,
    )


def readiness_for_organization(organization, *, now=None):
    now = now or timezone.now()
    settings = PeriodicExamSettings.objects.filter(organization=organization).first()
    cycle = PeriodicExamCycle.objects.filter(
        organization=organization, starts_at__lte=now, ends_at__gt=now
    ).first()
    if cycle:
        question_counts = dict(
            cycle.question_pool.values('level').annotate(total=Count('id')).values_list('level', 'total')
        )
        learner_counts = dict(
            cycle.participants.values('level_snapshot').annotate(total=Count('id')).values_list('level_snapshot', 'total')
        )
        required = cycle.questions_per_exam
        cutoff = cycle.starts_at
    else:
        raw_counts = question_counts_for_organizations([organization.id])[organization.id]
        question_counts = {row['level']: row['question_count'] for row in raw_counts}
        cutoff = settings.enabled_from if settings and settings.enabled_from else now
        learner_counts = dict(
            User.objects.filter(
                organization=organization,
                is_active=True,
                role=User.Role.LEARNER,
                is_demo=False,
                assessment_level__isnull=False,
                date_joined__lt=cutoff,
            ).exclude(assessment_level='').values('assessment_level').annotate(total=Count('id')).values_list(
                'assessment_level', 'total'
            )
        )
        required = settings.questions_per_exam if settings else PeriodicExamSettings._meta.get_field(
            'questions_per_exam'
        ).get_default()
    levels = []
    for level, label in User.AssessmentLevel.choices:
        count = question_counts.get(level, 0)
        can_form = count >= required
        levels.append({
            'level': level,
            'level_display': label,
            'unique_question_count': count,
            'eligible_learner_count': learner_counts.get(level, 0),
            'questions_per_exam': required,
            'can_form_full_exam': can_form,
            'note': '' if can_form else f'Cannot form a full exam: {count} unique questions available; {required} required.',
        })
    return {'organization_id': organization.id, 'cycle_id': cycle.id if cycle else None, 'as_of': cutoff, 'levels': levels}


def _promote_pending_frequency(settings, now):
    if settings.pending_frequency and settings.pending_frequency_effective_at <= now:
        settings.frequency = settings.pending_frequency
        settings.pending_frequency = None
        settings.pending_frequency_effective_at = None
        settings.save(update_fields=['frequency', 'pending_frequency', 'pending_frequency_effective_at', 'updated_at'])


def ensure_current_cycle(organization, now=None):
    """Create only the cycle containing ``now``; never backfill missed cycles."""
    now = now or timezone.now()
    with transaction.atomic():
        settings = get_or_create_settings(organization)
        settings = PeriodicExamSettings.objects.select_for_update().get(pk=settings.pk)
        if not settings.enabled or not settings.enabled_from or now < settings.enabled_from:
            return None

        _promote_pending_frequency(settings, now)
        boundary = period_for(settings.frequency, now)
        if boundary.starts_at < settings.enabled_from or not (boundary.starts_at <= now < boundary.ends_at):
            return None

        existing = PeriodicExamCycle.objects.filter(
            organization=organization, starts_at=boundary.starts_at
        ).first()
        if existing:
            return existing

        sequence = (
            PeriodicExamCycle.objects.filter(organization=organization).aggregate(Max('sequence'))['sequence__max'] or 0
        ) + 1
        values = {
            'sequence': sequence,
            'frequency_snapshot': settings.frequency,
            'configuration_version': settings.configuration_version,
            'questions_per_exam': settings.questions_per_exam,
            'pass_mark_percent': settings.pass_mark_percent,
            'seconds_per_question': settings.seconds_per_question,
            'max_attempts_per_cycle': settings.max_attempts_per_cycle,
            'reminders_enabled': settings.reminders_enabled,
            'reminder_days_before_end': settings.reminder_days_before_end,
            'starts_at': boundary.starts_at,
            'ends_at': boundary.ends_at,
            'start_date_ad': boundary.start_date_ad,
            'end_date_ad': boundary.end_date_ad,
            'start_year_bs': boundary.start_bs.year,
            'start_month_bs': boundary.start_bs.month,
            'start_day_bs': boundary.start_bs.day,
            'end_year_bs': boundary.end_bs.year,
            'end_month_bs': boundary.end_bs.month,
            'end_day_bs': boundary.end_bs.day,
            'fiscal_year_start_bs': boundary.fiscal_year_start_bs,
            'period_number': boundary.period_number,
            'display_label': boundary.display_label,
        }
        try:
            with transaction.atomic():
                cycle = PeriodicExamCycle.objects.create(organization=organization, **values)
                _materialize_cycle(cycle, now)
                return cycle
        except IntegrityError:
            return PeriodicExamCycle.objects.get(organization=organization, starts_at=boundary.starts_at)


def set_feature_enabled(organization, enabled, actor, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        row = get_or_create_settings(organization)
        row = PeriodicExamSettings.objects.select_for_update().get(pk=row.pk)
        if row.enabled == enabled:
            return row
        if enabled:
            current = PeriodicExamCycle.objects.filter(
                organization=organization, starts_at__lte=now, ends_at__gt=now
            ).first()
            row.enabled = True
            row.enabled_at = now
            row.disabled_at = None
            row.enabled_from = current.starts_at if current else next_full_period_start(row.frequency, now)
        else:
            row.enabled = False
            row.disabled_at = now
        row.updated_by = actor
        row.save()
        return row


def update_operational_settings(row, validated_data, actor, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        row = PeriodicExamSettings.objects.select_for_update().get(pk=row.pk)
        if row.enabled:
            ensure_current_cycle(row.organization, now)
            row.refresh_from_db()

        requested_frequency = validated_data.pop('frequency', row.frequency)
        frequency_changed = requested_frequency != row.frequency
        current = PeriodicExamCycle.objects.filter(
            organization=row.organization, starts_at__lte=now, ends_at__gt=now
        ).first()
        if frequency_changed:
            if current:
                row.pending_frequency = requested_frequency
                row.pending_frequency_effective_at = first_full_period_start_on_or_after(
                    requested_frequency, current.ends_at
                )
            else:
                row.frequency = requested_frequency
                row.pending_frequency = None
                row.pending_frequency_effective_at = None
                if row.enabled:
                    row.enabled_from = next_full_period_start(requested_frequency, now)

        changed = frequency_changed or any(getattr(row, field) != value for field, value in validated_data.items())
        for field, value in validated_data.items():
            setattr(row, field, value)
        if changed:
            row.configuration_version += 1
        row.updated_by = actor
        row.save()
        return row


KATHMANDU = ZoneInfo('Asia/Kathmandu')


def grade_selection(selected_option_keys, correct_option_keys):
    """Pure exact-set grading shared by manual and timeout transitions."""
    return set(selected_option_keys) == set(correct_option_keys)


def _learner_access_settings(user, *, require_enabled=True, now=None):
    now = now or timezone.now()
    if (
        user.role != User.Role.LEARNER
        or not user.is_active
        or user.is_demo
        or not user.organization_id
    ):
        raise PeriodicExamError('Periodic Exam is not available.', code='NOT_ELIGIBLE', status_code=403)
    settings = PeriodicExamSettings.objects.filter(organization_id=user.organization_id).first()
    if settings is None or (require_enabled and not settings.enabled):
        raise PeriodicExamError('Periodic Exam is disabled.', code='FEATURE_DISABLED', status_code=403)
    if user.organization.settings.is_access_locked_for(user, now.astimezone(KATHMANDU).date()):
        raise PeriodicExamError(
            "Your organization's subscription has expired.",
            code='SUBSCRIPTION_EXPIRED',
            status_code=403,
        )
    return settings


def _validate_participant_access(user, participant, *, now=None):
    _learner_access_settings(user, now=now)
    if participant.learner_id != user.id or participant.cycle.organization_id != user.organization_id:
        raise PeriodicExamError('Not found.', code='NOT_FOUND', status_code=404)
    if participant.revoked_at is not None:
        raise PeriodicExamError('Periodic Exam access has been revoked.', code='REVOKED', status_code=403)


def _randomized_age_order(rows, *, age_key, rng):
    ordered = []
    for _age, group in groupby(sorted(rows, key=age_key), key=age_key):
        tied = list(group)
        rng.shuffle(tied)
        ordered.extend(tied)
    return ordered


def select_questions_for_participant(participant, *, now=None, rng=None):
    """Select one paper without repetition, honoring lifetime/current-cycle history."""
    now = now or timezone.now()
    rng = rng or random.SystemRandom()
    cycle = participant.cycle
    pool = list(PeriodicExamCycleQuestion.objects.filter(
        cycle=cycle, level=participant.level_snapshot
    ))
    if len(pool) < cycle.questions_per_exam:
        raise PeriodicExamError(
            f'Cannot form a full exam: {len(pool)} unique questions available; '
            f'{cycle.questions_per_exam} required.',
            code='INSUFFICIENT_POOL',
        )

    current_cycle_keys = set(PeriodicExamAttemptQuestion.objects.filter(
        attempt__participant=participant,
    ).values_list('cycle_question__normalized_text_hash', flat=True))
    usages = {
        usage.question_key: usage
        for usage in PeriodicExamQuestionUsage.objects.select_for_update().filter(
            learner_id=participant.learner_id,
            level=participant.level_snapshot,
        )
    }
    lifetime_unused = [question for question in pool if question.normalized_text_hash not in usages]
    rng.shuffle(lifetime_unused)
    unused_this_cycle = [
        question for question in pool
        if question.normalized_text_hash in usages
        and question.normalized_text_hash not in current_cycle_keys
    ]
    used_this_cycle = [
        question for question in pool if question.normalized_text_hash in current_cycle_keys
    ]

    def age(question):
        usage = usages[question.normalized_text_hash]
        return usage.last_cycle_sequence, usage.last_used_at

    candidates = lifetime_unused
    candidates += _randomized_age_order(unused_this_cycle, age_key=age, rng=rng)
    candidates += _randomized_age_order(used_this_cycle, age_key=age, rng=rng)
    selected = candidates[:cycle.questions_per_exam]
    rng.shuffle(selected)
    return selected, usages


def _record_question_usage(participant, questions, usages, *, now):
    new_rows = []
    changed = []
    for question in questions:
        usage = usages.get(question.normalized_text_hash)
        if usage is None:
            new_rows.append(PeriodicExamQuestionUsage(
                learner_id=participant.learner_id,
                level=participant.level_snapshot,
                question_key=question.normalized_text_hash,
                first_cycle_sequence=participant.cycle.sequence,
                last_cycle_sequence=participant.cycle.sequence,
                last_used_at=now,
                times_used=1,
            ))
        else:
            usage.last_cycle_sequence = participant.cycle.sequence
            usage.last_used_at = now
            usage.times_used += 1
            changed.append(usage)
    PeriodicExamQuestionUsage.objects.bulk_create(new_rows, batch_size=SNAPSHOT_BATCH_SIZE)
    if changed:
        PeriodicExamQuestionUsage.objects.bulk_update(
            changed, ['last_cycle_sequence', 'last_used_at', 'times_used'], batch_size=SNAPSHOT_BATCH_SIZE
        )


def start_periodic_exam_attempt(user, *, now=None, rng=None):
    now = now or timezone.now()
    _learner_access_settings(user, now=now)
    cycle = ensure_current_cycle(user.organization, now)
    if cycle is None or now >= cycle.ends_at:
        raise PeriodicExamError('No Periodic Exam cycle is open.', code='CYCLE_CLOSED')

    with transaction.atomic():
        participant = PeriodicExamParticipant.objects.select_for_update().select_related('cycle').filter(
            cycle=cycle, learner=user
        ).first()
        if participant is None:
            raise PeriodicExamError('You are not eligible for this cycle.', code='NOT_ELIGIBLE', status_code=403)
        _validate_participant_access(user, participant, now=now)
        if participant.passed_at is not None:
            raise PeriodicExamError('This cycle has already been passed.', code='ALREADY_PASSED')
        open_attempt = participant.attempts.filter(submitted_at__isnull=True).first()
        if open_attempt is not None:
            return open_attempt, False
        attempts_started = participant.attempts.count()
        if attempts_started >= cycle.max_attempts_per_cycle:
            raise PeriodicExamError('Maximum attempts for this cycle have been used.', code='ATTEMPT_LIMIT_REACHED')
        if not participant.can_form_full_exam:
            available = cycle.question_pool.filter(level=participant.level_snapshot).count()
            raise PeriodicExamError(
                f'Cannot form a full exam: {available} unique questions available; '
                f'{cycle.questions_per_exam} required.',
                code='INSUFFICIENT_POOL',
            )

        selected, usages = select_questions_for_participant(participant, now=now, rng=rng)
        attempt = PeriodicExamAttempt.objects.create(
            participant=participant,
            attempt_number=attempts_started + 1,
            started_at=now,
            timer_segment_started_at=now,
        )
        PeriodicExamAttemptQuestion.objects.bulk_create([
            PeriodicExamAttemptQuestion(attempt=attempt, cycle_question=question, order=order)
            for order, question in enumerate(selected)
        ], batch_size=SNAPSHOT_BATCH_SIZE)
        _record_question_usage(participant, selected, usages, now=now)
        return attempt, True


def remaining_seconds_for_periodic_attempt(attempt, *, now=None):
    if attempt.submitted_at is not None:
        return 0
    now = now or timezone.now()
    elapsed = (now - attempt.timer_segment_started_at).total_seconds()
    return max(0, math.ceil(attempt.participant.cycle.seconds_per_question - elapsed))


def _lock_attempt_question(row, *, locked_at):
    if row.locked_at is not None:
        return row
    row.is_correct = grade_selection(
        row.selected_option_keys,
        row.cycle_question.correct_option_keys,
    )
    row.marks_awarded = row.cycle_question.marks if row.is_correct else 0
    row.locked_at = locked_at
    row.save(update_fields=['is_correct', 'marks_awarded', 'locked_at'])
    return row


def _finalize_attempt(attempt, *, submitted_at, reason):
    if attempt.submitted_at is not None:
        return attempt
    rows = list(attempt.paper_questions.select_related('cycle_question').order_by('order'))
    total_marks = sum(row.cycle_question.marks for row in rows)
    earned_marks = sum(row.marks_awarded for row in rows)
    score = Decimal('0.00') if total_marks == 0 else (
        (Decimal(earned_marks) * Decimal('100')) / Decimal(total_marks)
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    attempt.score_percent = score
    attempt.passed = score >= attempt.participant.cycle.pass_mark_percent
    attempt.submitted_at = submitted_at
    attempt.submission_reason = reason
    attempt.save(update_fields=['score_percent', 'passed', 'submitted_at', 'submission_reason'])

    participant = PeriodicExamParticipant.objects.select_for_update().get(pk=attempt.participant_id)
    participant.attempts_used = participant.attempts.count()
    if participant.best_score_percent is None or score > participant.best_score_percent:
        participant.best_score_percent = score
    if attempt.passed and participant.passed_at is None:
        participant.passed_at = submitted_at
    participant.last_attempt_at = submitted_at
    participant.save(update_fields=[
        'attempts_used', 'best_score_percent', 'passed_at', 'last_attempt_at'
    ])
    attempt.participant = participant
    return attempt


def catch_up_periodic_attempt(attempt, *, now=None):
    """Lock every elapsed question in sequence and auto-submit after the last."""
    if attempt.submitted_at is not None:
        return attempt
    now = now or timezone.now()
    rows = list(attempt.paper_questions.select_related('cycle_question').order_by('order'))
    seconds = attempt.participant.cycle.seconds_per_question
    elapsed = (now - attempt.timer_segment_started_at).total_seconds()
    index = attempt.current_question_index
    segment_start = attempt.timer_segment_started_at
    changed = False
    while elapsed >= seconds and index < len(rows):
        lock_time = segment_start + timedelta(seconds=seconds)
        _lock_attempt_question(rows[index], locked_at=lock_time)
        elapsed -= seconds
        segment_start = lock_time
        index += 1
        changed = True
    if index >= len(rows):
        return _finalize_attempt(
            attempt, submitted_at=segment_start,
            reason=PeriodicExamAttempt.SubmissionReason.QUESTION_TIMEOUT,
        )
    if changed:
        attempt.current_question_index = index
        attempt.timer_segment_started_at = segment_start
        attempt.save(update_fields=['current_question_index', 'timer_segment_started_at'])
    return attempt


def _locked_owned_attempt(user, attempt_id, *, now=None):
    now = now or timezone.now()
    attempt = PeriodicExamAttempt.objects.select_for_update().select_related(
        'participant__cycle'
    ).filter(
        pk=attempt_id,
        participant__learner=user,
        participant__cycle__organization_id=user.organization_id,
    ).first()
    if attempt is None:
        raise PeriodicExamError('Not found.', code='NOT_FOUND', status_code=404)
    _validate_participant_access(user, attempt.participant, now=now)
    return attempt


def get_periodic_attempt(user, attempt_id, *, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        attempt = _locked_owned_attempt(user, attempt_id, now=now)
        return catch_up_periodic_attempt(attempt, now=now)


def save_periodic_answer(user, attempt_id, *, current_question_index, selected_option_keys, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        attempt = _locked_owned_attempt(user, attempt_id, now=now)
        attempt = catch_up_periodic_attempt(attempt, now=now)
        if attempt.submitted_at is not None:
            raise PeriodicExamError('This attempt has already been submitted.', code='ALREADY_SUBMITTED')
        if current_question_index != attempt.current_question_index:
            raise PeriodicExamError('This question is no longer active.', code='STALE_QUESTION')
        row = attempt.paper_questions.select_related('cycle_question').get(order=attempt.current_question_index)
        if row.locked_at is not None:
            raise PeriodicExamError('This question is locked.', code='QUESTION_LOCKED')
        valid_keys = {choice['key'] for choice in row.cycle_question.choices}
        selected = list(dict.fromkeys(selected_option_keys))
        if any(key not in valid_keys for key in selected):
            raise PeriodicExamError('A selected option does not belong to this question.', code='INVALID_OPTION')
        if row.cycle_question.question_type == LevelQuestion.QuestionType.SINGLE_CHOICE and len(selected) > 1:
            raise PeriodicExamError('Select at most one option.', code='INVALID_SELECTION')
        row.selected_option_keys = selected
        row.save(update_fields=['selected_option_keys'])
        return attempt


def advance_periodic_attempt(user, attempt_id, *, current_question_index, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        attempt = _locked_owned_attempt(user, attempt_id, now=now)
        attempt = catch_up_periodic_attempt(attempt, now=now)
        if attempt.submitted_at is not None:
            return attempt
        if current_question_index < attempt.current_question_index:
            return attempt
        if current_question_index != attempt.current_question_index:
            raise PeriodicExamError('Cannot advance out of sequence.', code='STALE_QUESTION')
        row = attempt.paper_questions.select_related('cycle_question').get(order=attempt.current_question_index)
        _lock_attempt_question(row, locked_at=now)
        if attempt.current_question_index + 1 >= attempt.paper_questions.count():
            return _finalize_attempt(
                attempt, submitted_at=now, reason=PeriodicExamAttempt.SubmissionReason.LEARNER
            )
        attempt.current_question_index += 1
        attempt.timer_segment_started_at = now
        attempt.save(update_fields=['current_question_index', 'timer_segment_started_at'])
        return attempt


def submit_periodic_attempt(user, attempt_id, *, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        attempt = _locked_owned_attempt(user, attempt_id, now=now)
        attempt = catch_up_periodic_attempt(attempt, now=now)
        if attempt.submitted_at is not None:
            return attempt
        if attempt.current_question_index + 1 != attempt.paper_questions.count():
            raise PeriodicExamError('Only the final question can submit the attempt.', code='NOT_ON_FINAL_QUESTION')
        row = attempt.paper_questions.select_related('cycle_question').get(order=attempt.current_question_index)
        _lock_attempt_question(row, locked_at=now)
        return _finalize_attempt(attempt, submitted_at=now, reason=PeriodicExamAttempt.SubmissionReason.LEARNER)


def periodic_attempt_payload(attempt, *, now=None):
    now = now or timezone.now()
    data = {
        'id': attempt.id,
        'attempt_number': attempt.attempt_number,
        'submitted': attempt.submitted_at is not None,
        'current_question_index': attempt.current_question_index,
        'total_questions': attempt.paper_questions.count(),
        'remaining_seconds': remaining_seconds_for_periodic_attempt(attempt, now=now),
    }
    if attempt.submitted_at is not None:
        data.update({'score_percent': attempt.score_percent, 'passed': attempt.passed})
        return data
    row = attempt.paper_questions.select_related('cycle_question').get(order=attempt.current_question_index)
    question = row.cycle_question
    data['current_question'] = {
        'id': row.id,
        'question_text': question.question_text,
        'question_type': question.question_type,
        'marks': question.marks,
        'choices': question.choices,
        'selected_option_keys': row.selected_option_keys,
    }
    return data


def periodic_exam_summary(user, *, now=None):
    now = now or timezone.now()
    _learner_access_settings(user, now=now)
    cycle = ensure_current_cycle(user.organization, now)
    if cycle is None:
        raise PeriodicExamError('No Periodic Exam cycle is open.', code='CYCLE_CLOSED', status_code=404)
    participant = PeriodicExamParticipant.objects.filter(cycle=cycle, learner=user).first()
    if participant is None:
        raise PeriodicExamError('You are not eligible for this cycle.', code='NOT_ELIGIBLE', status_code=403)
    _validate_participant_access(user, participant, now=now)
    open_attempt = participant.attempts.filter(submitted_at__isnull=True).first()
    attempts_started = participant.attempts.count()
    reason = None
    if participant.passed_at is not None:
        reason = 'ALREADY_PASSED'
    elif participant.revoked_at is not None:
        reason = 'REVOKED'
    elif open_attempt is not None:
        reason = 'ATTEMPT_IN_PROGRESS'
    elif attempts_started >= cycle.max_attempts_per_cycle:
        reason = 'ATTEMPT_LIMIT_REACHED'
    elif not participant.can_form_full_exam:
        reason = 'INSUFFICIENT_POOL'
    elif now >= cycle.ends_at:
        reason = 'CYCLE_CLOSED'
    return {
        'cycle': {
            'id': cycle.id,
            'display_label': cycle.display_label,
            'starts_at': cycle.starts_at,
            'ends_at': cycle.ends_at,
        },
        'attempted': attempts_started > 0,
        'completed': participant.attempts.filter(submitted_at__isnull=False).exists(),
        'attempts_used': participant.attempts_used,
        'attempts_remaining': max(0, cycle.max_attempts_per_cycle - attempts_started),
        'best_score_percent': participant.best_score_percent,
        'passed': participant.passed_at is not None,
        'open_attempt_id': open_attempt.id if open_attempt else None,
        'can_start': reason is None,
        'reason_code': reason,
    }
