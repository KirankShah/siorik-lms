from django.conf import settings
from django.db import models

from courses.models import Slide


class SlideNarration(models.Model):
    """
    AI-generated spoken narration (script + audio) for a Slide, one row per
    language. unique_together on (slide, language) means a slide can have
    zero, one, or both languages generated independently — generating/
    regenerating one language never touches the other. See
    narration.services.generate_slide_narration for the generation pipeline
    (Claude for script_text, Azure Neural TTS for audio_file).
    """

    class Language(models.TextChoices):
        EN = 'en', 'English'
        NE = 'ne', 'Nepali'

    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='narrations')
    language = models.CharField(max_length=5, choices=Language.choices)
    script_text = models.TextField(blank=True, default='')
    audio_file = models.FileField(upload_to='slide_narrations/audio/', blank=True, null=True)
    # The fixed Azure Neural voice used for this row's language (platform-wide,
    # not user-selectable) — recorded per-row rather than read live from a
    # settings constant so past narrations still show which voice actually
    # produced their audio if the platform default is changed later.
    voice_name = models.CharField(max_length=100, blank=True, default='')
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('slide', 'language')

    def __str__(self):
        return f'{self.slide} narration ({self.language})'
