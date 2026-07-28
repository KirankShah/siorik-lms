from django.contrib import admin

from .models import Assignment, AssignmentSubmission


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('slide', 'submission_type', 'max_marks', 'due_offset_days')
    list_filter = ('submission_type',)
    search_fields = ('slide__title',)


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'user', 'submitted_at', 'marks_awarded', 'graded_at')
    list_filter = ('assignment',)
    search_fields = ('user__email', 'assignment__slide__title')
