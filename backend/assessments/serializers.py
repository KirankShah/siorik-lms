import random

from rest_framework import serializers

from accounts.models import User

from .models import Choice, Question, Quiz, QuizAnswer, QuizAttempt

PRIVILEGED_ROLES = (User.Role.INSTRUCTOR, User.Role.ORG_ADMIN, User.Role.PLATFORM_ADMIN)


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'choice_text', 'is_correct']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request is None or request.user.role not in PRIVILEGED_ROLES:
            data.pop('is_correct', None)
        return data


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'question_text', 'question_type', 'order', 'points', 'choices']


class QuizSummarySerializer(serializers.ModelSerializer):
    """Lightweight quiz representation for nesting under a page, without questions."""

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'pass_percentage', 'time_limit_minutes', 'max_attempts']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id',
            'page',
            'title',
            'pass_percentage',
            'time_limit_minutes',
            'max_attempts',
            'randomize_questions',
            'questions',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.randomize_questions:
            random.shuffle(data['questions'])
        return data


class QuizWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = [
            'id',
            'page',
            'title',
            'pass_percentage',
            'time_limit_minutes',
            'max_attempts',
            'randomize_questions',
        ]


class QuestionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'quiz', 'question_text', 'question_type', 'order', 'points']


class ChoiceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'question', 'choice_text', 'is_correct']


class QuizAnswerInputSerializer(serializers.Serializer):
    question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all())
    selected_choices = serializers.PrimaryKeyRelatedField(
        queryset=Choice.objects.all(), many=True, required=False, default=list
    )

    def validate(self, attrs):
        quiz = self.context['quiz']
        question = attrs['question']
        if question.quiz_id != quiz.id:
            raise serializers.ValidationError('Question does not belong to this quiz.')
        for choice in attrs['selected_choices']:
            if choice.question_id != question.id:
                raise serializers.ValidationError('Selected choice does not belong to the given question.')
        return attrs


class QuizSubmitSerializer(serializers.Serializer):
    answers = QuizAnswerInputSerializer(many=True)

    def validate_answers(self, answers):
        quiz = self.context['quiz']
        question_ids = [answer['question'].id for answer in answers]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError('Duplicate answers for the same question are not allowed.')
        expected_question_ids = set(quiz.questions.values_list('id', flat=True))
        if set(question_ids) != expected_question_ids:
            raise serializers.ValidationError('Answers must cover exactly the questions in this quiz.')
        return answers


class QuizAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAnswer
        fields = ['id', 'question', 'selected_choices', 'is_correct']


class QuizAttemptSerializer(serializers.ModelSerializer):
    answers = QuizAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'user',
            'quiz',
            'started_at',
            'submitted_at',
            'score_percent',
            'passed',
            'attempt_number',
            'answers',
        ]
