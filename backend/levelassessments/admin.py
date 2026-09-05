from django.contrib import admin

from .models import AssessmentLevel, LevelAssessmentAttempt, LevelChoice, LevelQuestion, QuestionSet


class LevelChoiceInline(admin.TabularInline):
    model = LevelChoice
    extra = 1


@admin.register(AssessmentLevel)
class AssessmentLevelAdmin(admin.ModelAdmin):
    list_display = ('organization', 'name', 'pass_threshold', 'questions_per_attempt')
    list_filter = ('organization', 'name')


@admin.register(QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display = ('assessment_level', 'label')
    list_filter = ('assessment_level__organization', 'assessment_level__name')


@admin.register(LevelQuestion)
class LevelQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_set', 'question_type', 'order', 'marks')
    list_filter = ('question_set__assessment_level__organization', 'question_type')
    inlines = [LevelChoiceInline]


@admin.register(LevelAssessmentAttempt)
class LevelAssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'assessment_level', 'started_at', 'submitted_at', 'score_percent', 'passed')
    list_filter = ('assessment_level__organization', 'assessment_level__name', 'passed')
    readonly_fields = ('questions_drawn',)
