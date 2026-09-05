from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from accounts.models import Organization, User
from assessments.models import AbstractGradedQuestion, AbstractOption

PERCENT_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class AssessmentLevel(models.Model):
    """
    A role-based knowledge-check tier for one organization — entirely
    independent of Course/Slide/Quiz (see LevelQuestion below); these are
    periodic knowledge checks tied to a learner's job role, not course
    content. `name` reuses accounts.User.AssessmentLevel's four values as
    the single source of truth, since a learner's own assessment_level says
    which of their organization's levels applies to them.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='assessment_levels')
    name = models.CharField(max_length=30, choices=User.AssessmentLevel.choices)
    pass_threshold = models.PositiveIntegerField(default=70, validators=PERCENT_VALIDATORS)
    # Configurable per level rather than a single global constant — Senior
    # Management may warrant more questions than Assistant/Supervisor.
    questions_per_attempt = models.PositiveIntegerField(default=15, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['organization', 'name']
        unique_together = ('organization', 'name')

    def __str__(self):
        return f'{self.organization.name} - {self.get_name_display()}'


class QuestionSet(models.Model):
    """
    An authoring-organization label only (e.g. "Set 1") — purely for the
    admin authoring UI to group questions into manageable batches. It has no
    runtime scoring meaning: an attempt draws from the full pool of
    LevelQuestion rows across all of a level's QuestionSets combined, so Set
    boundaries never affect which questions a learner sees (see
    levelassessments.services.start_level_assessment_attempt).
    """

    assessment_level = models.ForeignKey(AssessmentLevel, on_delete=models.CASCADE, related_name='question_sets')
    label = models.CharField(max_length=150)

    class Meta:
        ordering = ['assessment_level', 'label']

    def __str__(self):
        return f'{self.assessment_level} - {self.label}'


class LevelQuestion(AbstractGradedQuestion):
    """
    Standalone-assessment counterpart to assessments.Question (Phase 4/13) —
    same authoring shape (shared via AbstractGradedQuestion), but tied to a
    QuestionSet instead of a Quiz/Slide, and restricted to the two question
    types a role-based knowledge check needs: SINGLE_CHOICE and
    MULTIPLE_ANSWER (no matching/ordering/hotspot/etc. — those exist for rich
    course content, not a knowledge check pulled from a flat question pool).
    """

    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = 'SINGLE_CHOICE', 'Single choice'
        MULTIPLE_ANSWER = 'MULTIPLE_ANSWER', 'Multiple answer'

    question_set = models.ForeignKey(QuestionSet, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
    )

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.question_set} - Q{self.pk}'


class LevelChoice(AbstractOption):
    """
    Standalone-assessment counterpart to assessments.Choice (Phase 4/13),
    reusing the same shared option shape (AbstractOption): choice_text is the
    option label, is_correct flags the correct option(s) — exactly one for
    SINGLE_CHOICE, one or more for MULTIPLE_ANSWER.
    """

    question = models.ForeignKey(LevelQuestion, on_delete=models.CASCADE, related_name='choices')

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.choice_text


class LevelAssessmentAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='level_assessment_attempts'
    )
    assessment_level = models.ForeignKey(AssessmentLevel, on_delete=models.CASCADE, related_name='attempts')
    # The specific random subset of LevelQuestion ids drawn for this attempt
    # (see services.start_level_assessment_attempt) — stored rather than
    # re-derived so a graded attempt's exact question set stays auditable
    # later even if the pool changes (questions added/edited/removed).
    questions_drawn = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    passed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            # Enforces "one attempt at a time in progress" at the database
            # level (the service layer also pre-checks this for a friendly
            # error message, but this is the real guarantee under a race).
            # A prior completed/failed attempt (submitted_at set) never
            # blocks a retake — only a currently-open one does.
            models.UniqueConstraint(
                fields=['user', 'assessment_level'],
                condition=models.Q(submitted_at__isnull=True),
                name='one_open_level_assessment_attempt_per_user_level',
            ),
        ]

    def __str__(self):
        return f'{self.user} - {self.assessment_level} ({self.started_at:%Y-%m-%d})'

    def calculate_score_percent(self):
        """
        Compute score_percent/passed from this attempt's LevelAssessmentAnswers
        and persist them — same shape as assessments.QuizAttempt's method of
        the same name, scored against this attempt's own questions_drawn
        (not the level's full, possibly-since-changed pool).
        """
        total_marks = LevelQuestion.objects.filter(id__in=self.questions_drawn).aggregate(total=Sum('marks'))[
            'total'
        ] or 0

        if total_marks == 0:
            self.score_percent = 0
        else:
            earned_marks = self.answers.filter(is_correct=True).aggregate(total=Sum('question__marks'))['total'] or 0
            self.score_percent = round((earned_marks / total_marks) * 100, 2)

        self.passed = self.score_percent >= self.assessment_level.pass_threshold
        self.submitted_at = self.submitted_at or timezone.now()
        self.save(update_fields=['score_percent', 'passed', 'submitted_at'])
        return self.score_percent


class LevelAssessmentAnswer(models.Model):
    """Standalone-assessment counterpart to assessments.QuizAnswer — much
    simpler since LevelQuestion is always choice-based (SINGLE_CHOICE or
    MULTIPLE_ANSWER), so a set of selected_choices plus is_correct is enough;
    none of QuizAnswer's other-question-type fields apply here."""

    attempt = models.ForeignKey(LevelAssessmentAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(LevelQuestion, on_delete=models.CASCADE, related_name='answers')
    selected_choices = models.ManyToManyField(LevelChoice, blank=True, related_name='selected_in_answers')
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['question__order', 'question_id']
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f'{self.attempt} - {self.question}'
