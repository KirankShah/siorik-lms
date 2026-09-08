from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Organization

from .services import ensure_assessment_levels_for_organization


@receiver(post_save, sender=Organization, dispatch_uid='seed_assessment_levels_for_new_org')
def seed_assessment_levels(sender, instance, created, **kwargs):
    """Give every new organization its four assessment tiers immediately, so
    an admin can import questions / assign staff to a level without a separate
    setup step. Existing orgs are backfilled by migration 0003."""
    if created:
        ensure_assessment_levels_for_organization(instance)
