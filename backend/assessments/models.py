from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from accounts.validators import validate_image_size
from courses.models import Slide

MAX_QUESTION_TEXT_LENGTH = 5_000


class AbstractGradedQuestion(models.Model):
    """
    Field shape shared between this app's Question (tied to a Quiz/Slide,
    Phase 4/13) and levelassessments.LevelQuestion (standalone, tied to a
    QuestionSet, Phase B) — same authoring shape, different parent container
    and question_type choices, so the common fields live here once instead of
    being redefined per model.
    """

    question_text = models.TextField(validators=[MaxLengthValidator(MAX_QUESTION_TEXT_LENGTH)])
    order = models.PositiveIntegerField(default=0)
    marks = models.PositiveIntegerField(default=1)
    explanation = models.TextField(blank=True, help_text='Rich text shown to the learner after answering.')
    feedback_correct = models.TextField(blank=True)
    feedback_incorrect = models.TextField(blank=True)

    class Meta:
        abstract = True


class AbstractOption(models.Model):
    """
    Field shape shared between this app's Choice (Phase 4/13) and
    levelassessments.LevelChoice (Phase B): choice_text is the option label,
    is_correct flags the correct option(s) — see each concrete model's own
    docstring for type-specific meaning beyond this shared shape.
    """

    choice_text = models.CharField(max_length=500, blank=True, default='')
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True


class Quiz(models.Model):
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255)
    # Per-quiz pass/fail indicator only (drives QuizAttempt.passed and what's
    # shown to the learner right after submitting). Certificate eligibility
    # is governed separately, by the course-wide average against
    # Course.certificate_pass_threshold — see
    # certificates.services.certificate_ineligibility_reason. A learner can
    # fail an individual quiz here and still earn the certificate.
    pass_percentage = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    max_attempts = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Null means unlimited attempts.',
    )
    randomize_questions = models.BooleanField(default=False)

    class Meta:
        ordering = ['slide', 'title']

    def __str__(self):
        return f'{self.slide.display_title()} - {self.title}'


class Question(AbstractGradedQuestion):
    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = 'SINGLE_CHOICE', 'Single choice'
        MULTIPLE_CHOICE = 'MULTIPLE_CHOICE', 'Multiple choice'
        MULTIPLE_ANSWER = 'MULTIPLE_ANSWER', 'Multiple answer'
        TRUE_FALSE = 'TRUE_FALSE', 'True/False'
        FILL_BLANK = 'FILL_BLANK', 'Fill in the blank'
        MATCHING = 'MATCHING', 'Matching'
        ORDERING = 'ORDERING', 'Ordering'
        CATEGORIZE = 'CATEGORIZE', 'Categorize'
        HOTSPOT = 'HOTSPOT', 'Hotspot'
        SHORT_ANSWER = 'SHORT_ANSWER', 'Short answer'
        ESSAY = 'ESSAY', 'Essay'

    class FillBlankMode(models.TextChoices):
        TEXT_INPUT = 'TEXT_INPUT', 'Text input'
        WORD_BANK = 'WORD_BANK', 'Word bank'

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
    )
    # FILL_BLANK-only — ignored by every other question type. question_text
    # may contain numbered placeholders like {{1}}, {{2}} for either mode;
    # TEXT_INPUT renders a text box per blank, WORD_BANK a drop target per
    # blank fed by a shuffled bank of draggable tokens (WordBankToken).
    fill_blank_mode = models.CharField(
        max_length=20,
        choices=FillBlankMode.choices,
        default=FillBlankMode.TEXT_INPUT,
    )
    points = models.PositiveIntegerField(default=1)
    image = models.ImageField(upload_to='question_images/', blank=True, null=True, validators=[validate_image_size])
    video_url = models.URLField(blank=True, null=True)

    class Meta:
        ordering = ['order']
        unique_together = ('quiz', 'order')

    def __str__(self):
        return f'{self.quiz.title} - Q{self.order}'


class Choice(AbstractOption):
    """
    A single "answer option" row, reused across several question types with
    different meaning per type rather than one table per type:

    - SINGLE_CHOICE / MULTIPLE_CHOICE / MULTIPLE_ANSWER / TRUE_FALSE:
      choice_text is the option label, is_correct flags correct option(s).
    - FILL_BLANK (TEXT_INPUT mode only — WORD_BANK mode uses WordBankToken
      instead): choice_text is one accepted answer, is_correct is always
      True, blank_index says which numbered {{N}} placeholder it answers
      (null defaults to blank 1, for questions with only one blank).
    - MATCHING: choice_text is the left-hand item, match_text is the correct
      right-hand pair.
    - ORDERING: choice_text is the item label, order is its correct position.
    - SHORT_ANSWER / ESSAY: no Choice rows — manually graded free text.
    """

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    match_text = models.CharField(max_length=500, blank=True, default='')
    blank_index = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.choice_text


class WordBankToken(models.Model):
    """A FILL_BLANK/WORD_BANK question's draggable token."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='word_bank_tokens')
    text = models.CharField(max_length=200, blank=True, default='')
    # Null means this token is a distractor, not the correct answer for any blank.
    correct_blank_index = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text


class CategoryBucket(models.Model):
    """A CATEGORIZE question's drop target, e.g. 'Predicate Offence'."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='buckets')
    label = models.CharField(max_length=255, blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.label


class CategorizeItem(models.Model):
    """A CATEGORIZE question's draggable item — text and/or image content."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='categorize_items')
    item_text = models.CharField(max_length=500, blank=True, default='')
    item_image = models.ImageField(upload_to='categorize_item_images/', blank=True, null=True, validators=[validate_image_size])
    correct_bucket = models.ForeignKey(CategoryBucket, on_delete=models.CASCADE, related_name='items')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.item_text or f'Item {self.pk}'


PERCENT_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class HotspotRegion(models.Model):
    """
    A HOTSPOT question's clickable rectangle, drawn over Question.image.
    x/y/width/height are percentages (0-100) of the image's own dimensions
    rather than fixed pixels, so a region drawn in the authoring UI still
    lines up correctly however large the image renders for the learner.
    """

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='hotspot_regions')
    x = models.FloatField(validators=PERCENT_VALIDATORS)
    y = models.FloatField(validators=PERCENT_VALIDATORS)
    width = models.FloatField(validators=PERCENT_VALIDATORS)
    height = models.FloatField(validators=PERCENT_VALIDATORS)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'Region {self.pk} on {self.question}'


class QuizAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    passed = models.BooleanField(default=False)
    attempt_number = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-started_at']
        unique_together = ('user', 'quiz', 'attempt_number')

    def calculate_score_percent(self):
        """Compute score_percent/passed from this attempt's QuizAnswers and persist them."""
        total_points = self.quiz.questions.aggregate(total=Sum('points'))['total'] or 0

        if total_points == 0:
            self.score_percent = 0
        else:
            earned_points = self.answers.filter(is_correct=True).aggregate(
                total=Sum('question__points')
            )['total'] or 0
            self.score_percent = round((earned_points / total_points) * 100, 2)

        self.passed = self.score_percent >= self.quiz.pass_percentage
        self.submitted_at = self.submitted_at or timezone.now()
        self.save(update_fields=['score_percent', 'passed', 'submitted_at'])
        return self.score_percent

    def __str__(self):
        return f'{self.user} - {self.quiz} (attempt {self.attempt_number})'


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    selected_choices = models.ManyToManyField(Choice, blank=True, related_name='selected_in_answers')
    # HOTSPOT-only — plays the same role selected_choices does for other
    # types, just against HotspotRegion instead of Choice.
    selected_regions = models.ManyToManyField(HotspotRegion, blank=True, related_name='selected_in_answers')
    # Free-text response for SHORT_ANSWER/ESSAY questions (manually graded —
    # see marks_awarded/grader_feedback/graded_at below).
    text_response = models.TextField(blank=True, default='')
    # CATEGORIZE-only: {categorize_item_id: category_bucket_id} learner
    # placements — plays the same role selected_choices does for other
    # types, just shaped as a mapping since it's item->bucket, not a set.
    category_placements = models.JSONField(blank=True, default=dict)
    # FILL_BLANK/TEXT_INPUT-only: {blank_index: typed text}.
    fill_blank_text = models.JSONField(blank=True, default=dict)
    # FILL_BLANK/WORD_BANK-only: {blank_index: word_bank_token_id}.
    word_bank_placements = models.JSONField(blank=True, default=dict)
    is_correct = models.BooleanField(default=False)
    # Manual grading, for SHORT_ANSWER/ESSAY — mirrors AssignmentSubmission's
    # marks_awarded/grader_feedback/graded_at in the assignments app.
    marks_awarded = models.PositiveIntegerField(null=True, blank=True)
    grader_feedback = models.TextField(blank=True, default='')
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['question__order']
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f'{self.attempt} - {self.question}'
