from django.contrib import admin

from .models import Choice, Question, Quiz, QuizAnswer, QuizAttempt


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'course',
        'pass_percentage',
        'time_limit_minutes',
        'max_attempts',
        'randomize_questions',
    )
    list_filter = ('course', 'randomize_questions')
    search_fields = ('title', 'course__title')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'quiz', 'question_type', 'order', 'points')
    list_filter = ('question_type', 'quiz')
    search_fields = ('question_text', 'quiz__title')
    inlines = [ChoiceInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'quiz',
        'attempt_number',
        'score_percent',
        'passed',
        'started_at',
        'submitted_at',
    )
    list_filter = ('passed', 'quiz')
    search_fields = ('user__email', 'quiz__title')


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'is_correct')
    list_filter = ('is_correct', 'question__quiz')
    search_fields = ('attempt__user__email', 'question__question_text')
