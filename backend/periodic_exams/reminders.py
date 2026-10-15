import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from accounts.models import User

from .models import PeriodicExamReminderDelivery, PeriodicExamSettings
from .services import ensure_current_cycle


logger = logging.getLogger(__name__)
KATHMANDU = ZoneInfo('Asia/Kathmandu')


def reminder_days_remaining(cycle, now):
    return (cycle.end_date_ad - now.astimezone(KATHMANDU).date()).days


def send_periodic_exam_reminder_email(participant, days_before_end):
    learner = participant.learner
    display_name = participant.name_snapshot or 'Learner'
    login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login"
    subject = f'Periodic Exam reminder — {participant.cycle.display_label}'
    text_body = (
        f'Dear {display_name},\n\n'
        f'Your {participant.cycle.display_label} Periodic Exam closes in '
        f'{days_before_end} day(s), on {participant.cycle.end_date_ad}.\n'
        'This reminder is sent because you have not yet passed this cycle.\n\n'
        f'Log in to Siorik LMS: {login_url}\n\n'
        'Best regards,\nSiorik Consultancy Pvt. Ltd.'
    )
    html_body = f'''
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 560px; margin: 0 auto;">
  <div style="background: #032147; color: white; padding: 20px 24px;">
    <h1 style="font-size: 20px; margin: 0;">Periodic Exam reminder</h1>
  </div>
  <div style="border: 1px solid #e5e7eb; border-top: 0; padding: 24px;">
    <p>Dear {escape(display_name)},</p>
    <p>Your <strong>{escape(participant.cycle.display_label)}</strong> Periodic Exam closes in
      <strong>{days_before_end} day(s)</strong>, on {participant.cycle.end_date_ad}.</p>
    <p>This reminder is sent because you have not yet passed this cycle.</p>
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


def _deliver(participant, days_before_end, now, email_sender):
    with transaction.atomic():
        delivery, _ = PeriodicExamReminderDelivery.objects.get_or_create(
            cycle=participant.cycle,
            participant=participant,
            days_before_end=days_before_end,
        )
        delivery = PeriodicExamReminderDelivery.objects.select_for_update().get(pk=delivery.pk)
        if delivery.sent_at is not None:
            return 'duplicate'
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        try:
            email_sender(participant, days_before_end)
        except Exception as exc:
            delivery.last_error = str(exc)[:2000]
            delivery.save(update_fields=['attempt_count', 'last_attempt_at', 'last_error'])
            logger.error(
                'Periodic Exam reminder failed: cycle=%s participant=%s days=%s',
                participant.cycle_id, participant.id, days_before_end,
            )
            return 'failed'
        delivery.sent_at = now
        delivery.last_error = ''
        delivery.save(update_fields=[
            'attempt_count', 'last_attempt_at', 'last_error', 'sent_at'
        ])
        logger.info(
            'Periodic Exam reminder sent: cycle=%s participant=%s days=%s',
            participant.cycle_id, participant.id, days_before_end,
        )
        return 'sent'


def send_due_periodic_exam_reminders(*, now=None, dry_run=False, email_sender=None):
    now = now or timezone.now()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError('A timezone-aware now value is required.')
    email_sender = email_sender or send_periodic_exam_reminder_email
    today = now.astimezone(KATHMANDU).date()
    result = {'due': 0, 'sent': 0, 'failed': 0, 'duplicate': 0, 'recipients': []}
    feature_rows = PeriodicExamSettings.objects.filter(
        enabled=True, organization__is_active=True
    ).select_related('organization', 'organization__settings')
    for feature in feature_rows.iterator():
        organization = feature.organization
        if organization.settings.is_subscription_expired(today):
            continue
        cycle = ensure_current_cycle(organization, now)
        if cycle is None or not cycle.reminders_enabled:
            continue
        days_before_end = reminder_days_remaining(cycle, now)
        if days_before_end not in cycle.reminder_days_before_end:
            continue
        participants = cycle.participants.filter(
            passed_at__isnull=True,
            revoked_at__isnull=True,
            learner__isnull=False,
            learner__is_active=True,
            learner__role=User.Role.LEARNER,
        ).select_related('learner', 'cycle').order_by('id')
        for participant in participants.iterator(chunk_size=500):
            result['due'] += 1
            result['recipients'].append(participant.id)
            if dry_run:
                continue
            outcome = _deliver(participant, days_before_end, now, email_sender)
            result[outcome] += 1
    return result
