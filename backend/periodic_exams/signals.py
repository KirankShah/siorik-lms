from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PeriodicExamAttempt
from .services import revoke_ineligible_participants

ELIGIBILITY_FIELDS = {'is_active', 'is_demo', 'role', 'organization', 'organization_id'}


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid='periodic_exam_revoke_on_user_save')
def revoke_on_user_change(sender, instance, created, update_fields=None, **kwargs):
    """Revoke a learner's open-cycle participation as soon as they become ineligible.

    Bulk ``QuerySet.update`` calls bypass this signal; the report, reminders and
    expiry command also sweep with ``revoke_ineligible_participants``.
    """
    if created:
        return
    if update_fields is not None and not ELIGIBILITY_FIELDS.intersection(update_fields):
        return
    revoke_ineligible_participants(learner=instance)


@receiver(post_save, sender=PeriodicExamAttempt, dispatch_uid='periodic_exam_refresh_leaderboard')
def refresh_leaderboard_on_submission(sender, instance, raw=False, update_fields=None, **kwargs):
    """Refresh current knowledge whenever any Periodic Exam attempt closes."""
    if raw or instance.submitted_at is None:
        return
    if update_fields is not None and 'submitted_at' not in update_fields:
        return
    learner = instance.participant.learner
    if learner is None:
        return

    # Deferred to avoid a module import cycle: gamification reads periodic
    # attempts when calculating the score, while this app owns submission.
    from gamification.services import refresh_current_knowledge_for_user

    refresh_current_knowledge_for_user(learner)
