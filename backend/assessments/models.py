from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from courses.models import Course


class Quiz(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
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
        ordering = ['course', 'title']

    def __str__(self):
        return f'{self.course.title} - {self.title}'


class Question(models.Model):
    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = 'SINGLE_CHOICE', 'Single choice'
        MULTIPLE_CHOICE = 'MULTIPLE_CHOICE', 'Multiple choice'
        TRUE_FALSE = 'TRUE_FALSE', 'True/False'

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
    )
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']
        unique_together = ('quiz', 'order')

    def __str__(self):
        return f'{self.quiz.title} - Q{self.order}'


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

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
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['question__order']
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f'{self.attempt} - {self.question}'
