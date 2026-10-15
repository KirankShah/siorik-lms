from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

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
