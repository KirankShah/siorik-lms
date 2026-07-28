from rest_framework import serializers

from accounts.serializers import UserSerializer

from .models import Assignment, AssignmentSubmission


class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ['id', 'slide', 'instructions', 'submission_type', 'max_marks', 'due_offset_days']


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    """Instructor grading view — everything but marks_awarded/grader_feedback is read-only."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id',
            'assignment',
            'user',
            'submitted_at',
            'file',
            'text_response',
            'marks_awarded',
            'grader_feedback',
            'graded_at',
        ]
        read_only_fields = ['id', 'assignment', 'user', 'submitted_at', 'file', 'text_response', 'graded_at']

    def validate_marks_awarded(self, value):
        max_marks = self.instance.assignment.max_marks
        if value is not None and value > max_marks:
            raise serializers.ValidationError(f'Cannot award more than the assignment\'s {max_marks} marks.')
        return value


class AssignmentSubmissionCreateSerializer(serializers.ModelSerializer):
    """Learner-facing submission — grading fields aren't settable here."""

    class Meta:
        model = AssignmentSubmission
        fields = ['id', 'assignment', 'submitted_at', 'file', 'text_response']
        read_only_fields = ['id', 'submitted_at']
