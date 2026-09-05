from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validate_image_size, validate_phone_number


class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='organization_logos/', blank=True, null=True, validators=[validate_image_size])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.PLATFORM_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        LEARNER = 'LEARNER', 'Learner'
        INSTRUCTOR = 'INSTRUCTOR', 'Instructor'
        ORG_ADMIN = 'ORG_ADMIN', 'Org Admin'
        PLATFORM_ADMIN = 'PLATFORM_ADMIN', 'Platform Admin'

    class NarrationLanguage(models.TextChoices):
        EN = 'en', 'English'
        NE = 'ne', 'Nepali'

    class AssessmentLevel(models.TextChoices):
        ASSISTANT_SUPERVISOR = 'assistant_supervisor', 'Assistant/Supervisor'
        OFFICER = 'officer', 'Officer'
        MANAGEMENT = 'management', 'Management'
        SENIOR_MANAGEMENT = 'senior_management', 'Senior Management'

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.LEARNER)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True, validators=[validate_phone_number])
    designation = models.CharField(max_length=150, blank=True, null=True)
    corporate_title = models.CharField(max_length=150, blank=True, null=True)
    functional_title = models.CharField(max_length=150, blank=True, null=True)
    branch_department = models.CharField(max_length=150, blank=True, null=True)
    # Nullable — not every user needs one (e.g. platform admins).
    assessment_level = models.CharField(
        max_length=30, choices=AssessmentLevel.choices, blank=True, null=True
    )
    # Provisioned via the admin "demo users" tool (accounts.services.provision_demo_user)
    # rather than self-registration — a marker, not a separate user type/table.
    is_demo = models.BooleanField(default=False)
    # Set on any account created with a system-generated temporary password;
    # cleared by SetPasswordView once the user picks their own. Frontend's
    # ProtectedRoute redirects to /reset-password for as long as this is True.
    must_reset_password = models.BooleanField(default=False)
    # The narration audio/script language the slide player defaults to for
    # this learner — see narration app (SlideNarration.Language mirrors these
    # same two codes). Settable by the learner themselves via MeView's PATCH.
    preferred_narration_language = models.CharField(
        max_length=5, choices=NarrationLanguage.choices, default=NarrationLanguage.EN
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email
