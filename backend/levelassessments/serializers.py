import random

from rest_framework import serializers

from accounts.serializers import OrganizationSerializer

from .models import AssessmentLevel, LevelAssessmentAnswer, LevelAssessmentAttempt, LevelChoice, LevelQuestion


class AssessmentLevelSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    name_display = serializers.CharField(source='get_name_display', read_only=True)

    class Meta:
        model = AssessmentLevel
        fields = ['id', 'organization', 'name', 'name_display', 'pass_threshold', 'questions_per_attempt']
        read_only_fields = fields


class LevelChoiceSerializer(serializers.ModelSerializer):
    """
    Learner-facing only — unlike assessments.ChoiceSerializer this never
    exposes is_correct at all (no privileged-viewer bypass, since there's no
    authoring/review context that reuses this serializer): a LevelQuestion is
    only ever fetched through a LevelAssessmentAttempt the viewer is actively
    sitting or has already submitted, and the answer key belongs on
    LevelAssessmentAnswerSerializer, scoped to a specific submitted answer,
    same separation as the quiz app's Choice/QuizAnswer split.
    """

    class Meta:
        model = LevelChoice
        fields = ['id', 'choice_text', 'order']


class LevelQuestionSerializer(serializers.ModelSerializer):
    choices = serializers.SerializerMethodField()

    class Meta:
        model = LevelQuestion
        fields = ['id', 'question_text', 'question_type', 'marks', 'choices']

    def get_choices(self, obj):
        # Stored `order` carries no answer-key meaning for these two question
        # types (just authoring/creation order) — shuffled here so a learner
        # can't exploit a positional pattern, same reasoning as
        # assessments.QuestionSerializer for its own choice-based types.
        choices = list(obj.choices.all())
        random.shuffle(choices)
        return LevelChoiceSerializer(choices, many=True).data


class LevelAssessmentAnswerSerializer(serializers.ModelSerializer):
    # Answer-key data revealed only for this specific answer, scoped to an
    # attempt the learner has already submitted — mirrors
    # assessments.QuizAnswerSerializer's exact reasoning.
    correct_choice_ids = serializers.SerializerMethodField()
    explanation = serializers.CharField(source='question.explanation', read_only=True)
    feedback_correct = serializers.CharField(source='question.feedback_correct', read_only=True)
    feedback_incorrect = serializers.CharField(source='question.feedback_incorrect', read_only=True)

    class Meta:
        model = LevelAssessmentAnswer
        fields = [
            'id',
            'question',
            'selected_choices',
            'is_correct',
            'correct_choice_ids',
            'explanation',
            'feedback_correct',
            'feedback_incorrect',
        ]

    def get_correct_choice_ids(self, obj):
        return list(obj.question.choices.filter(is_correct=True).values_list('id', flat=True))


class LevelAssessmentAttemptSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    answers = LevelAssessmentAnswerSerializer(many=True, read_only=True)
    assessment_level_name = serializers.CharField(source='assessment_level.get_name_display', read_only=True)
    pass_threshold = serializers.IntegerField(source='assessment_level.pass_threshold', read_only=True)

    class Meta:
        model = LevelAssessmentAttempt
        fields = [
            'id',
            'user',
            'assessment_level',
            'assessment_level_name',
            'pass_threshold',
            'started_at',
            'submitted_at',
            'score_percent',
            'passed',
            'questions',
            'answers',
        ]
        read_only_fields = fields

    def get_questions(self, obj):
        # Preserves the attempt's own stored draw order (already randomized
        # by random.sample at start time) rather than re-sorting — and
        # tolerates a question having since been deleted from the pool
        # (skipped, rather than erroring) since questions_drawn is a frozen
        # snapshot, not a live relation.
        questions_by_id = LevelQuestion.objects.filter(id__in=obj.questions_drawn).prefetch_related('choices').in_bulk()
        ordered = [questions_by_id[question_id] for question_id in obj.questions_drawn if question_id in questions_by_id]
        return LevelQuestionSerializer(ordered, many=True, context=self.context).data


class LevelAssessmentAnswerInputSerializer(serializers.Serializer):
    question = serializers.PrimaryKeyRelatedField(queryset=LevelQuestion.objects.all())
    selected_choices = serializers.PrimaryKeyRelatedField(queryset=LevelChoice.objects.all(), many=True, required=False, default=list)

    def validate(self, attrs):
        attempt = self.context['attempt']
        question = attrs['question']
        if question.id not in attempt.questions_drawn:
            raise serializers.ValidationError('Question was not part of this attempt.')
        for choice in attrs['selected_choices']:
            if choice.question_id != question.id:
                raise serializers.ValidationError('Selected choice does not belong to the given question.')
        return attrs


class LevelAssessmentSubmitSerializer(serializers.Serializer):
    answers = LevelAssessmentAnswerInputSerializer(many=True)

    def validate_answers(self, answers):
        attempt = self.context['attempt']
        question_ids = [answer['question'].id for answer in answers]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError('Duplicate answers for the same question are not allowed.')
        if set(question_ids) != set(attempt.questions_drawn):
            raise serializers.ValidationError('Answers must cover exactly the questions drawn for this attempt.')
        return answers
