from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from accounts.validators import validate_image_size
from courses.models import Page

MAX_QUESTION_TEXT_LENGTH = 5_000


class Quiz(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255)
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
        ordering = ['page', 'title']

    def __str__(self):
        return f'{self.page.title} - {self.title}'


class Question(models.Model):
    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = 'SINGLE_CHOICE', 'Single choice'
        MULTIPLE_CHOICE = 'MULTIPLE_CHOICE', 'Multiple choice'
        MULTIPLE_ANSWER = 'MULTIPLE_ANSWER', 'Multiple answer'
        TRUE_FALSE = 'TRUE_FALSE', 'True/False'
        FILL_BLANK = 'FILL_BLANK', 'Fill in the blank'
        MATCHING = 'MATCHING', 'Matching'
        ORDERING = 'ORDERING', 'Ordering'
        SHORT_ANSWER = 'SHORT_ANSWER', 'Short answer'
        ESSAY = 'ESSAY', 'Essay'

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField(validators=[MaxLengthValidator(MAX_QUESTION_TEXT_LENGTH)])
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
    )
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1)
    image = models.ImageField(upload_to='question_images/', blank=True, null=True, validators=[validate_image_size])
    video_url = models.URLField(blank=True, null=True)
    explanation = models.TextField(blank=True, help_text='Rich text shown to the learner after answering.')
    marks = models.PositiveIntegerField(default=1)
    feedback_correct = models.TextField(blank=True)
    feedback_incorrect = models.TextField(blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ('quiz', 'order')

    def __str__(self):
        return f'{self.quiz.title} - Q{self.order}'


class Choice(models.Model):
    """
    A single "answer option" row, reused across several question types with
    different meaning per type rather than one table per type:

    - SINGLE_CHOICE / MULTIPLE_CHOICE / MULTIPLE_ANSWER / TRUE_FALSE:
      choice_text is the option label, is_correct flags correct option(s).
    - FILL_BLANK: choice_text is one accepted answer; is_correct is always True.
    - MATCHING: choice_text is the left-hand item, match_text is the correct
      right-hand pair.
    - ORDERING: choice_text is the item label, order is its correct position.
    - SHORT_ANSWER / ESSAY: no Choice rows — manually graded free text.
    """

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    match_text = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.choice_text


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
    # Free-text response for FILL_BLANK/SHORT_ANSWER/ESSAY questions.
    text_response = models.TextField(blank=True, default='')
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
