from .models import CertificateTemplate


def editable_certificate_templates_for_user(user):
    """
    CertificateTemplate rows a given user is allowed to manage — mirrors
    courses.permissions.editable_courses_for_user's exact scoping shape:

    - PLATFORM_ADMIN: every template, including every organization's own and
      the platform-level (organization=None) ones.
    - ORG_ADMIN/INSTRUCTOR: only their own organization's template — never
      another organization's, and never the platform-level template (that's
      a platform-wide branding asset, not theirs to change).
    - LEARNER: none.
    """
    if user.role == user.Role.PLATFORM_ADMIN:
        return CertificateTemplate.objects.all()

    if user.role in (user.Role.ORG_ADMIN, user.Role.INSTRUCTOR):
        return CertificateTemplate.objects.filter(organization_id=user.organization_id)

    return CertificateTemplate.objects.none()
