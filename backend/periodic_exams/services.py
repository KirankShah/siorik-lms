from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from accounts.models import User
from levelassessments.models import LevelQuestion
from levelassessments.services import normalize_question_text

from .calendar import first_full_period_start_on_or_after, next_full_period_start, period_for
from .models import PeriodicExamCycle, PeriodicExamSettings


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
                return PeriodicExamCycle.objects.create(organization=organization, **values)
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
