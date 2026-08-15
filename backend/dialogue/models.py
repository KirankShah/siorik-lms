from django.core.validators import FileExtensionValidator
from django.db import models

from accounts.validators import validate_image_size

from .services import crop_to_opaque_bounds

# PNG/SVG only — a straight illustration-pack asset, not a photo, so raster
# formats beyond PNG aren't needed. FileField (not ImageField) because
# Pillow's ImageField validation can't open SVG (it's XML, not raster data).
ILLUSTRATION_FILE_VALIDATORS = [validate_image_size, FileExtensionValidator(allowed_extensions=['png', 'svg'])]


class Character(models.Model):
    """
    A reusable illustrated character for the Dialogue element (see
    courses.Element.ElementType.DIALOGUE) — one pose per character, sourced
    from a single consistent illustration pack. Platform-wide content,
    loaded once via the Django admin as a one-time step (not something
    instructors manage per course), then picked by name in the Dialogue
    element's authoring UI.
    """

    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Customer'
        TELLER = 'TELLER', 'Teller'
        COMPLIANCE_OFFICER = 'COMPLIANCE_OFFICER', 'Compliance Officer'
        BRANCH_MANAGER = 'BRANCH_MANAGER', 'Branch Manager'
        OTHER = 'OTHER', 'Other'

    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices)
    avatar_image = models.FileField(upload_to='character_avatars/', validators=ILLUSTRATION_FILE_VALIDATORS)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        cropped = crop_to_opaque_bounds(self.avatar_image) if self.avatar_image else None
        if cropped is not None:
            self.avatar_image.save(self.avatar_image.name, cropped, save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.get_role_display()})'


class Scene(models.Model):
    """A reusable illustrated background for the Dialogue element — see Character's docstring for the same
    platform-wide, seeded-once-via-admin sourcing.
    """

    class SceneType(models.TextChoices):
        FRONT_OFFICE = 'FRONT_OFFICE', 'Front office'
        BACK_OFFICE = 'BACK_OFFICE', 'Back office'

    name = models.CharField(max_length=100)
    scene_type = models.CharField(max_length=20, choices=SceneType.choices)
    background_image = models.FileField(upload_to='scene_backgrounds/', validators=ILLUSTRATION_FILE_VALIDATORS)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
