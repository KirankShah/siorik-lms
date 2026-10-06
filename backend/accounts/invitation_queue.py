from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from audit.services import log_action

from .models import StaffInvitation, StaffInvitationJob
from .services import generate_temp_password, send_staff_learner_invite_email


def process_next_staff_invitation_batch(*, batch_size=None, minimum_interval=None):
    """Send one durable invitation batch and never exceed the hourly allowance."""
    batch_size = batch_size or settings.STAFF_INVITATION_BATCH_SIZE
    minimum_interval = minimum_interval or timedelta(seconds=settings.STAFF_INVITATION_BATCH_INTERVAL_SECONDS)
    now = timezone.now()

    with transaction.atomic():
        job = (
            StaffInvitationJob.objects.select_for_update()
            .filter(status__in=[StaffInvitationJob.Status.QUEUED, StaffInvitationJob.Status.PROCESSING])
            .order_by('created_at')
            .first()
        )
        if job is None:
            return {'status': 'idle', 'sent': 0}
        if job.status == StaffInvitationJob.Status.PROCESSING:
            if job.last_batch_started_at and now >= job.last_batch_started_at + minimum_interval:
                # A previous command was interrupted. Sent items were committed
                # one by one, so safely resume only the remaining pending rows.
                job.status = StaffInvitationJob.Status.QUEUED
                job.save(update_fields=['status'])
            else:
                return {'status': 'already_processing', 'job_id': job.pk, 'sent': 0}
        if job.last_batch_started_at and now < job.last_batch_started_at + minimum_interval:
            return {
                'status': 'waiting', 'job_id': job.pk, 'sent': 0,
                'next_run_at': job.last_batch_started_at + minimum_interval,
            }
        invitation_ids = list(
            job.invitations.filter(status=StaffInvitation.Status.PENDING)
            .order_by('created_at').values_list('pk', flat=True)[:batch_size]
        )
        if not invitation_ids:
            job.status = StaffInvitationJob.Status.COMPLETE
            job.completed_at = now
            job.save(update_fields=['status', 'completed_at'])
            return {'status': 'complete', 'job_id': job.pk, 'sent': 0}
        job.status = StaffInvitationJob.Status.PROCESSING
        job.last_batch_started_at = now
        job.error = ''
        job.save(update_fields=['status', 'last_batch_started_at', 'error'])

    sent = 0
    for invitation_id in invitation_ids:
        try:
            with transaction.atomic():
                invitation = StaffInvitation.objects.select_for_update().select_related('user', 'job').get(
                    pk=invitation_id
                )
                if invitation.status != StaffInvitation.Status.PENDING:
                    continue
                temporary_password = generate_temp_password()
                invitation.user.set_password(temporary_password)
                invitation.user.must_reset_password = True
                invitation.user.save(update_fields=['password', 'must_reset_password'])
                send_staff_learner_invite_email(invitation.user, temporary_password)
                invitation.status = StaffInvitation.Status.SENT
                invitation.attempts += 1
                invitation.sent_at = timezone.now()
                invitation.last_error = ''
                invitation.save(update_fields=['status', 'attempts', 'sent_at', 'last_error'])
                log_action(invitation.job.requested_by, AuditLog.Action.STAFF_ENROLLED, invitation.user)
                sent += 1
        except Exception as exc:
            with transaction.atomic():
                invitation = StaffInvitation.objects.select_for_update().select_related('job').get(pk=invitation_id)
                invitation.status = StaffInvitation.Status.FAILED
                invitation.attempts += 1
                invitation.last_error = str(exc)[:2000]
                invitation.save(update_fields=['status', 'attempts', 'last_error'])
                job = invitation.job
                job.status = StaffInvitationJob.Status.FAILED
                job.error = f'Invitation failed for {invitation.user.email}: {exc}'[:2000]
                job.sent_count = job.invitations.filter(status=StaffInvitation.Status.SENT).count()
                job.save(update_fields=['status', 'error', 'sent_count'])
            return {'status': 'failed', 'job_id': job.pk, 'sent': sent, 'error': job.error}

    with transaction.atomic():
        job = StaffInvitationJob.objects.select_for_update().get(pk=job.pk)
        job.sent_count = job.invitations.filter(status=StaffInvitation.Status.SENT).count()
        if job.invitations.filter(status=StaffInvitation.Status.PENDING).exists():
            job.status = StaffInvitationJob.Status.QUEUED
            result_status = 'batch_complete'
        else:
            job.status = StaffInvitationJob.Status.COMPLETE
            job.completed_at = timezone.now()
            result_status = 'complete'
        job.save(update_fields=['status', 'sent_count', 'completed_at'])
    return {'status': result_status, 'job_id': job.pk, 'sent': sent, 'total_sent': job.sent_count}
