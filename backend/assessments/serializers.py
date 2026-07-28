import random

from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserSerializer

from .models import CategorizeItem, CategoryBucket, Choice, HotspotRegion, Question, Quiz, QuizAnswer, QuizAttempt

PRIVILEGED_ROLES = (User.Role.INSTRUCTOR, User.Role.ORG_ADMIN, User.Role.PLATFORM_ADMIN)


class CategoryBucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryBucket
        fields = ['id', 'label', 'order']


class CategorizeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategorizeItem
        fields = ['id', 'item_text', 'item_image', 'correct_bucket', 'order']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request is None or request.user.role not in PRIVILEGED_ROLES:
            # correct_bucket *is* the answer key for this item.
            data.pop('correct_bucket', None)
        return data


class HotspotRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotspotRegion
        fields = ['id', 'x', 'y', 'width', 'height', 'is_correct']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request is None or request.user.role not in PRIVILEGED_ROLES:
            data.pop('is_correct', None)
        return data


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'choice_text', 'is_correct', 'order', 'match_text']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request is None or request.user.role not in PRIVILEGED_ROLES:
            # is_correct and match_text both directly reveal the answer key
            # (for MATCHING, match_text *is* the correct pairing).
            data.pop('is_correct', None)
            data.pop('match_text', None)
            # For ORDERING, `order` *is* the answer key (the correct sequence)
            # rather than just a display hint like it is for other types.
            if instance.question.question_type == Question.QuestionType.ORDERING:
                data.pop('order', None)
        return data


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)
    match_targets = serializers.SerializerMethodField()
    buckets = CategoryBucketSerializer(many=True, read_only=True)
    categorize_items = CategorizeItemSerializer(many=True, read_only=True)
    hotspot_regions = HotspotRegionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id',
            'question_text',
            'question_type',
            'order',
            'points',
            'image',
            'video_url',
            'explanation',
            'marks',
            'feedback_correct',
            'feedback_incorrect',
            'choices',
            'match_targets',
            'buckets',
            'categorize_items',
            'hotspot_regions',
        ]

    def get_match_targets(self, obj):
        """
        MATCHING's right-hand pool: one {id, text} per Choice, `id` reused
        from the owning Choice so a correct drop is simply id === id — but
        text is deliberately never bundled back onto its own choice_text in
        the same object (see ChoiceSerializer), so the pairing isn't visible
        by inspecting a single row of the response.
        """
        if obj.question_type != Question.QuestionType.MATCHING:
            return None
        targets = [{'id': choice.id, 'text': choice.match_text} for choice in obj.choices.all()]
        request = self.context.get('request')
        if request is None or request.user.role not in PRIVILEGED_ROLES:
            random.shuffle(targets)
        return targets

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request is None or request.user.role not in PRIVILEGED_ROLES:
            # These all give away the answer (or reveal it before the learner
            # has submitted), same reasoning as Choice.is_correct above.
            data.pop('explanation', None)
            data.pop('feedback_correct', None)
            data.pop('feedback_incorrect', None)
            if instance.question_type != Question.QuestionType.MATCHING:
                data.pop('match_targets', None)
            # ORDERING's `order` *is* the answer key (stripped per-choice
            # above already) — the display order of `choices` itself would
            # still give it away outright, so shuffle it too.
            if instance.question_type == Question.QuestionType.ORDERING:
                random.shuffle(data['choices'])
            # CATEGORIZE items are usually authored bucket-by-bucket, so
            # their natural order would otherwise cluster each bucket's
            # correct answers together — shuffle to break that up.
            if instance.question_type == Question.QuestionType.CATEGORIZE:
                random.shuffle(data['categorize_items'])
        return data


class QuizSummarySerializer(serializers.ModelSerializer):
    """Lightweight quiz representation for nesting under a slide, without questions."""

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'pass_percentage', 'time_limit_minutes', 'max_attempts']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id',
            'slide',
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
            'slide',
            'title',
            'pass_percentage',
            'time_limit_minutes',
            'max_attempts',
            'randomize_questions',
        ]


class QuestionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id',
            'quiz',
            'question_text',
            'question_type',
            'order',
            'points',
            'image',
            'video_url',
            'explanation',
            'marks',
            'feedback_correct',
            'feedback_incorrect',
        ]


class ChoiceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'question', 'choice_text', 'is_correct', 'order', 'match_text']


class CategoryBucketWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryBucket
        fields = ['id', 'question', 'label', 'order']


class CategorizeItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategorizeItem
        fields = ['id', 'question', 'item_text', 'item_image', 'correct_bucket', 'order']


class HotspotRegionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotspotRegion
        fields = ['id', 'question', 'x', 'y', 'width', 'height', 'is_correct']


class CategoryPlacementInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=CategorizeItem.objects.all())
    bucket = serializers.PrimaryKeyRelatedField(queryset=CategoryBucket.objects.all())


class QuizAnswerInputSerializer(serializers.Serializer):
    question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all())
    selected_choices = serializers.PrimaryKeyRelatedField(
        queryset=Choice.objects.all(), many=True, required=False, default=list
    )
    # CATEGORIZE-only — see QuizAnswer.category_placements.
    category_placements = CategoryPlacementInputSerializer(many=True, required=False, default=list)
    # HOTSPOT-only — see QuizAnswer.selected_regions.
    selected_regions = serializers.PrimaryKeyRelatedField(
        queryset=HotspotRegion.objects.all(), many=True, required=False, default=list
    )

    def validate(self, attrs):
        quiz = self.context['quiz']
        question = attrs['question']
        if question.quiz_id != quiz.id:
            raise serializers.ValidationError('Question does not belong to this quiz.')
        for choice in attrs['selected_choices']:
            if choice.question_id != question.id:
                raise serializers.ValidationError('Selected choice does not belong to the given question.')
        for placement in attrs['category_placements']:
            if placement['item'].question_id != question.id or placement['bucket'].question_id != question.id:
                raise serializers.ValidationError('Category placement does not belong to the given question.')
        for region in attrs['selected_regions']:
            if region.question_id != question.id:
                raise serializers.ValidationError('Selected region does not belong to the given question.')
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
    # The quiz itself (QuizSerializer/QuestionSerializer/ChoiceSerializer)
    # strips is_correct/explanation/feedback for learners so the answer key
    # isn't visible while a quiz is in progress. Once an attempt exists,
    # though, the learner has already committed their answers, so it's safe
    # — and it's what the results screen needs — to surface the answer key
    # for this question right here, scoped to just this one attempt/answer.
    correct_choice_ids = serializers.SerializerMethodField()
    correct_order = serializers.SerializerMethodField()
    correct_placements = serializers.SerializerMethodField()
    correct_region_ids = serializers.SerializerMethodField()
    explanation = serializers.CharField(source='question.explanation', read_only=True)
    feedback_correct = serializers.CharField(source='question.feedback_correct', read_only=True)
    feedback_incorrect = serializers.CharField(source='question.feedback_incorrect', read_only=True)

    class Meta:
        model = QuizAnswer
        fields = [
            'id',
            'question',
            'selected_choices',
            'category_placements',
            'selected_regions',
            'is_correct',
            'correct_choice_ids',
            'correct_order',
            'correct_placements',
            'correct_region_ids',
            'explanation',
            'feedback_correct',
            'feedback_incorrect',
        ]

    def get_correct_choice_ids(self, obj):
        return list(obj.question.choices.filter(is_correct=True).values_list('id', flat=True))

    def get_correct_order(self, obj):
        # Only meaningful for ORDERING — `order` is never exposed pre-submit
        # (see ChoiceSerializer/QuestionSerializer), so this is the one place
        # the correct sequence is safe to reveal, scoped to this one answer.
        if obj.question.question_type != Question.QuestionType.ORDERING:
            return None
        return list(obj.question.choices.order_by('order', 'id').values_list('id', flat=True))

    def get_correct_placements(self, obj):
        # Only meaningful for CATEGORIZE — correct_bucket is never exposed
        # pre-submit (see CategorizeItemSerializer), same reasoning as above.
        if obj.question.question_type != Question.QuestionType.CATEGORIZE:
            return None
        return {item.id: item.correct_bucket_id for item in obj.question.categorize_items.all()}

    def get_correct_region_ids(self, obj):
        return list(obj.question.hotspot_regions.filter(is_correct=True).values_list('id', flat=True))


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


class GradingQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'question_text', 'question_type', 'marks']


class QuizAnswerGradingSerializer(serializers.ModelSerializer):
    """Instructor grading view for manually-graded SHORT_ANSWER/ESSAY answers."""

    question = GradingQuestionSerializer(read_only=True)
    user = UserSerializer(source='attempt.user', read_only=True)
    quiz_title = serializers.CharField(source='attempt.quiz.title', read_only=True)

    class Meta:
        model = QuizAnswer
        fields = [
            'id',
            'question',
            'user',
            'quiz_title',
            'text_response',
            'marks_awarded',
            'grader_feedback',
            'graded_at',
        ]
        read_only_fields = ['id', 'question', 'user', 'quiz_title', 'text_response', 'graded_at']

    def validate_marks_awarded(self, value):
        question = self.instance.question
        if value is not None and value > question.marks:
            raise serializers.ValidationError(f'Cannot award more than the question\'s {question.marks} marks.')
        return value
