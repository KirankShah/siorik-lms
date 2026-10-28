import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape

from accounts.models import User

from .models import PeriodicExamReminderDelivery, PeriodicExamSettings
from .services import (
    close_expired_periodic_attempts,
    ensure_current_cycle,
    revoke_ineligible_participants,
)


logger = logging.getLogger(__name__)
KATHMANDU = ZoneInfo('Asia/Kathmandu')
ACTIVATION_DELIVERY_KEY = 0
DEADLINE_REMINDER_DAYS = 7


def reminder_days_remaining(cycle, now):
    return (cycle.end_date_ad - now.astimezone(KATHMANDU).date()).days


def _send_email(participant, *, subject, heading, message):
    learner = participant.learner
    display_name = participant.name_snapshot or 'Learner'
    login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/periodic-exam?cycle={participant.cycle_id}"
    text_body = (
        f'Dear {display_name},\n\n'
        f'{message}\n\n'
        f'Log in to Siorik LMS: {login_url}\n\n'
        'Best regards,\nSiorik Consultancy Pvt. Ltd.'
    )
    html_body = f'''
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 560px; margin: 0 auto;">
  <div style="background: #032147; color: white; padding: 20px 24px;">
    <h1 style="font-size: 20px; margin: 0;">{escape(heading)}</h1>
  </div>
  <div style="border: 1px solid #e5e7eb; border-top: 0; padding: 24px;">
    <p>Dear {escape(display_name)},</p>
    <p>{escape(message)}</p>
    <p style="margin: 24px 0;"><a href="{escape(login_url)}" style="background: #e1b862; color: #032147; padding: 11px 18px; text-decoration: none; font-weight: bold;">Log in to Siorik LMS</a></p>
    <p>Best regards,<br>Siorik Consultancy Pvt. Ltd.</p>
  </div>
</div>'''
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[learner.email],
    )
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


def send_periodic_exam_notification_email(participant, delivery_key):
    label = participant.cycle.display_label
    if delivery_key == ACTIVATION_DELIVERY_KEY:
        _send_email(
            participant,
            subject=f'{label} Periodic Exam is now active',
            heading='Periodic Exam activated',
            message=(
                f'The {label} Periodic Exam has been activated. '
                'Please log in to Siorik LMS to access and complete your Periodic Exam.'
            ),
        )
        return

    retake = participant.attempts_used > 0
    action = 'requires a retake' if retake else 'is still pending'
    _send_email(
        participant,
        subject=f'{label} Periodic Exam {"retake" if retake else "reminder"}',
        heading='Periodic Exam reminder',
        message=(
            f'Your {label} Periodic Exam {action}. The exam month ends in '
            f'{DEADLINE_REMINDER_DAYS} days, on {participant.cycle.end_date_ad}. '
            'Please log in to Siorik LMS to complete it.'
        ),
    )


def _deliver(participant, delivery_key, now, email_sender):
    # Claim the ledger row and commit BEFORE sending, so a rollback can never
    # undo the record of an email that already went out. A claimed row with no
    # sent_at and no error (in flight, or a crash mid-send) is never retried
    # automatically: a possibly-missed reminder beats a possible duplicate.
    with transaction.atomic():
        delivery, _ = PeriodicExamReminderDelivery.objects.get_or_create(
            cycle=participant.cycle,
            participant=participant,
            days_before_end=delivery_key,
        )
        delivery = PeriodicExamReminderDelivery.objects.select_for_update().get(pk=delivery.pk)
        if delivery.sent_at is not None:
            return 'duplicate'
        if delivery.last_attempt_at is not None and not delivery.last_error:
            return 'duplicate'
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        delivery.last_error = ''
        delivery.save(update_fields=['attempt_count', 'last_attempt_at', 'last_error'])

    try:
        email_sender(participant, delivery_key)
    except Exception as exc:
        PeriodicExamReminderDelivery.objects.filter(pk=delivery.pk).update(
            last_error=str(exc)[:2000] or exc.__class__.__name__
        )
        logger.error(
            'Periodic Exam reminder failed: cycle=%s participant=%s days=%s',
            participant.cycle_id, participant.id, delivery_key,
        )
        return 'failed'
    PeriodicExamReminderDelivery.objects.filter(pk=delivery.pk).update(sent_at=now)
    logger.info(
        'Periodic Exam reminder sent: cycle=%s participant=%s days=%s',
        participant.cycle_id, participant.id, delivery_key,
    )
    return 'sent'


def send_due_periodic_exam_reminders(*, now=None, dry_run=False, email_sender=None, max_deliveries=None):
    now = now or timezone.now()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError('A timezone-aware now value is required.')
    email_sender = email_sender or send_periodic_exam_notification_email
    max_deliveries = max_deliveries or getattr(settings, 'PERIODIC_EXAM_EMAIL_BATCH_SIZE', 50)
    if type(max_deliveries) is not int or max_deliveries < 1:
        raise ValueError('max_deliveries must be a positive integer.')
    delivery_budget = max_deliveries
    today = now.astimezone(KATHMANDU).date()
    result = {
        'due': 0, 'activation_due': 0, 'deadline_due': 0,
        'sent': 0, 'failed': 0, 'duplicate': 0, 'remaining': 0, 'recipients': [],
    }
    feature_rows = PeriodicExamSettings.objects.filter(
        enabled=True, organization__is_active=True
    ).select_related('organization', 'organization__settings')
    for feature in feature_rows.iterator():
        organization = feature.organization
        if organization.settings.is_subscription_expired(today):
            continue
        cycle = ensure_current_cycle(organization, now)
        if cycle is None:
            continue
        if not dry_run:
            # An expired attempt may have passed; close it so that learner is excluded.
            close_expired_periodic_attempts(cycle=cycle, now=now)
            revoke_ineligible_participants(cycle=cycle, now=now)
        participants = cycle.participants.filter(
            revoked_at__isnull=True,
            learner__isnull=False,
            learner__is_active=True,
            learner__role=User.Role.LEARNER,
        ).select_related('learner', 'cycle').order_by('id')

        def unsent(queryset, delivery_key):
            delivered_ids = PeriodicExamReminderDelivery.objects.filter(
                cycle=cycle, days_before_end=delivery_key, sent_at__isnull=False,
            ).values_list('participant_id', flat=True)
            return queryset.exclude(pk__in=delivered_ids)

        activation = unsent(participants, ACTIVATION_DELIVERY_KEY)
        deadline = participants.none()
        if reminder_days_remaining(cycle, now) == DEADLINE_REMINDER_DAYS:
            # The seven-day reminder is only actionable for learners who have
            # not passed and can still submit or resume an attempt. Exhausted
            # failures are final and receive no misleading retake reminder.
            incomplete = participants.filter(passed_at__isnull=True).filter(
                Q(attempts_used__lt=cycle.max_attempts_per_cycle)
                | Q(attempts__submitted_at__isnull=True)
            ).distinct()
            deadline = unsent(incomplete, DEADLINE_REMINDER_DAYS)

        activation_count = activation.count()
        deadline_count = deadline.count()
        result['activation_due'] += activation_count
        result['deadline_due'] += deadline_count
        result['due'] += activation_count + deadline_count

        if dry_run:
            result['recipients'].extend(deadline.values_list('id', flat=True))
            result['recipients'].extend(activation.values_list('id', flat=True))
            continue

        # Deadline reminders are more urgent than overdue activation notices.
        # A single global budget is shared across every organization so the
        # sending domain stays below its hourly provider quota.
        for queryset, delivery_key in (
            (deadline, DEADLINE_REMINDER_DAYS),
            (activation, ACTIVATION_DELIVERY_KEY),
        ):
            for participant in queryset.iterator(chunk_size=500):
                if delivery_budget <= 0:
                    break
                outcome = _deliver(participant, delivery_key, now, email_sender)
                result[outcome] += 1
                if outcome in ('sent', 'failed'):
                    delivery_budget -= 1
            if delivery_budget <= 0:
                break
    result['remaining'] = max(0, result['due'] - result['sent'] - result['duplicate'])
    return result
