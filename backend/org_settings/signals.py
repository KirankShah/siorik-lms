from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Organization

from .models import OrganizationSettings


@receiver(post_save, sender=Organization, dispatch_uid='seed_organization_settings_for_new_org')
def seed_organization_settings(sender, instance, created, **kwargs):
    """Give every new organization its settings row immediately, so
    organization.settings is never missing — mirrors
    levelassessments.signals' seed_assessment_levels. Existing orgs are
    backfilled by migration 0002."""
    if created:
        OrganizationSettings.objects.get_or_create(organization=instance)
