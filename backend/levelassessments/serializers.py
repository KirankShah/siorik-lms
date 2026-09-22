import random

from rest_framework import serializers

from accounts.serializers import OrganizationSerializer

from .imports import OPTION_LETTERS, parse_correct_answers, parse_marks
from .imports import validate_options as _validate_question_options
from .models import AssessmentLevel, LevelAssessmentAnswer, LevelAssessmentAttempt, LevelChoice, LevelQuestion
from .services import remaining_seconds_for_attempt


class AssessmentLevelSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    name_display = serializers.CharField(source='get_name_display', read_only=True)
    # Sourced from org_settings.OrganizationSettings (one row per
    # organization, shared by all four of its levels) rather than a column on
    # this model — see AssessmentLevel's own docstring. Read-only here: edited
    # only from the Organization Settings screen, never per level.
    pass_threshold = serializers.IntegerField(source='organization.settings.pass_mark_percent', read_only=True)
    questions_per_attempt = serializers.IntegerField(
        source='organization.settings.questions_per_attempt', read_only=True
    )
    timing_mode = serializers.CharField(source='organization.settings.timing_mode', read_only=True)
    seconds_per_question = serializers.IntegerField(
        source='organization.settings.seconds_per_question', read_only=True
    )
    total_exam_minutes = serializers.IntegerField(
        source='organization.settings.total_exam_minutes', read_only=True
    )

    class Meta:
        model = AssessmentLevel
        fields = [
            'id', 'organization', 'name', 'name_display',
            'pass_threshold', 'questions_per_attempt', 'timing_mode', 'seconds_per_question', 'total_exam_minutes',
        ]
        # The four tiers are fixed per org (seeded on org creation); their
        # scoring config now lives entirely on OrganizationSettings, so every
        # field here is read-only (see org_settings.views.OrganizationSettingsViewSet
        # for the actual write path).
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


def _choices_by_option_letter(question):
    """{letter: LevelChoice | None} for a question's up-to-5 options — A-E
    map to LevelChoice.order 0-4 (see imports._create_question, the only
    place LevelChoice rows are ever created; a blank option simply has no
    row, not a row with blank text). Shared by the two admin serializers
    below so the letter<->order mapping is defined exactly once."""
    by_order = {choice.order: choice for choice in question.choices.all()}
    return {letter: by_order.get(index) for index, letter in enumerate(OPTION_LETTERS)}


class LevelQuestionListSerializer(serializers.ModelSerializer):
    """
    Row shape for the Question Bank admin list (levelassessments.views.
    LevelQuestionAdminViewSet.list) — deliberately not the learner-facing
    LevelQuestionSerializer above (which strips is_correct entirely): this
    is an admin authoring surface, so the correct answer is exactly what the
    admin is scanning the table for. Full editable detail is fetched
    separately via retrieve, same fetch-on-demand convention as the rest of
    the app.
    """

    question_set_label = serializers.CharField(source='question_set.label', read_only=True)
    assessment_level_name = serializers.CharField(
        source='question_set.assessment_level.get_name_display', read_only=True
    )
    organization_name = serializers.CharField(
        source='question_set.assessment_level.organization.name', read_only=True
    )
    correct_answers = serializers.SerializerMethodField()

    class Meta:
        model = LevelQuestion
        fields = [
            'id', 'question_set_label', 'assessment_level_name', 'organization_name',
            'question_text', 'question_type', 'correct_answers', 'marks',
        ]

    def get_correct_answers(self, obj):
        return [choice.choice_text for choice in obj.choices.all() if choice.is_correct]


class LevelQuestionDetailSerializer(serializers.ModelSerializer):
    """
    Full record for the Question Bank admin "View/Edit" panel — read-only;
    the write path is LevelQuestionEditSerializer below (this is also what
    a successful edit re-serializes back to the frontend). `options` is
    keyed by letter (A-E) rather than 5 flat fields — a blank string for any
    letter with no LevelChoice row, so the edit form always has exactly the
    same 5 keys to render regardless of how many options this question uses.
    """

    question_set_label = serializers.CharField(source='question_set.label', read_only=True)
    assessment_level_name = serializers.CharField(
        source='question_set.assessment_level.get_name_display', read_only=True
    )
    options = serializers.SerializerMethodField()
    correct_answers = serializers.SerializerMethodField()

    class Meta:
        model = LevelQuestion
        fields = [
            'id', 'question_set', 'question_set_label', 'assessment_level_name',
            'question_text', 'question_type', 'options', 'correct_answers',
            'marks', 'explanation', 'feedback_correct', 'feedback_incorrect',
        ]
        read_only_fields = fields

    def get_options(self, obj):
        return {
            letter: (choice.choice_text if choice else '')
            for letter, choice in _choices_by_option_letter(obj).items()
        }

    def get_correct_answers(self, obj):
        return [letter for letter, choice in _choices_by_option_letter(obj).items() if choice and choice.is_correct]


class LevelQuestionEditSerializer(serializers.Serializer):
    """
    Write side of the Question Bank "View/Edit" panel
    (levelassessments.views.LevelQuestionAdminViewSet.partial_update).
    Deliberately reuses imports.py's own row-validation functions
    (parse_correct_answers, parse_marks, validate_options) rather than
    reimplementing the acceptance rules, so an edit can never leave a
    question in a state the Excel bulk import would have rejected.
    """

    question_text = serializers.CharField()
    question_type = serializers.ChoiceField(choices=LevelQuestion.QuestionType.choices)
    options = serializers.DictField(child=serializers.CharField(allow_blank=True))
    correct_answers = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    marks = serializers.IntegerField()
    explanation = serializers.CharField(allow_blank=True, required=False, default='')
    feedback_correct = serializers.CharField(allow_blank=True, required=False, default='')
    feedback_incorrect = serializers.CharField(allow_blank=True, required=False, default='')

    def validate_options(self, value):
        unknown = set(value) - set(OPTION_LETTERS)
        if unknown:
            raise serializers.ValidationError(f'Unknown option letter(s): {", ".join(sorted(unknown))}.')
        return {letter: value.get(letter, '') for letter in OPTION_LETTERS}

    def validate(self, attrs):
        correct_letters, error = parse_correct_answers(','.join(attrs['correct_answers']), attrs['question_type'])
        if error:
            raise serializers.ValidationError({'correct_answers': error})

        options_error = _validate_question_options(attrs['options'], correct_letters)
        if options_error:
            raise serializers.ValidationError({'correct_answers': options_error})

        marks, marks_error = parse_marks(str(attrs['marks']))
        if marks_error:
            raise serializers.ValidationError({'marks': marks_error})

        attrs['correct_letters'] = correct_letters
        attrs['marks'] = marks
        return attrs


class LevelAssessmentAnswerSerializer(serializers.ModelSerializer):
    # Answer-key data revealed only for this specific answer, scoped to an
    # attempt the learner has already submitted — mirrors
    # assessments.QuizAnswerSerializer's exact reasoning.
    correct_choice_ids = serializers.SerializerMethodField()
    is_unanswered = serializers.SerializerMethodField()
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
            'is_unanswered',
            'correct_choice_ids',
            'explanation',
            'feedback_correct',
            'feedback_incorrect',
        ]

    def get_correct_choice_ids(self, obj):
        return list(obj.question.choices.filter(is_correct=True).values_list('id', flat=True))

    def get_is_unanswered(self, obj):
        """An empty selection is a timed-out/unreached question, not a wrong answer.

        The sequential UI does not allow learners to skip an unanswered
        question manually, so the only graded empty selections are questions
        whose per-question timer expired or which remained when the overall
        exam timer submitted the attempt. They still earn zero marks because
        is_correct remains false.
        """
        return not obj.selected_choices.exists()


class LevelAssessmentAttemptSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    answers = LevelAssessmentAnswerSerializer(many=True, read_only=True)
    assessment_level_name = serializers.CharField(source='assessment_level.get_name_display', read_only=True)
    pass_threshold = serializers.IntegerField(
        source='assessment_level.organization.settings.pass_mark_percent', read_only=True
    )
    # Resume support (see the model's own field docstrings and
    # levelassessments.services.resume_level_assessment_attempt):
    # current_question_index/answers_so_far let the frontend restore exactly
    # where the learner left off; remaining_seconds is computed fresh on
    # every serialization (never stored) from timer_segment_started_at, so
    # it's correct for a freshly-started attempt, a live one, or one just
    # resumed after time away — the frontend seeds its own client-side
    # countdown from this single value in every case, fresh start included.
    remaining_seconds = serializers.SerializerMethodField()

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
            'current_question_index',
            'answers_so_far',
            'remaining_seconds',
            'questions',
            'answers',
        ]
        read_only_fields = fields

    def get_remaining_seconds(self, obj):
        if obj.submitted_at is not None:
            return 0
        return remaining_seconds_for_attempt(obj)

    def get_questions(self, obj):
        # Preserves the attempt's own stored draw order (already randomized
        # by random.sample at start time) rather than re-sorting. Tolerates a
        # question having since been deleted from the pool (e.g. via the
        # Question Bank admin surface) since questions_drawn is a frozen
        # snapshot, not a live relation — a removed one is represented by a
        # `removed: true` placeholder in its original position, rather than
        # silently dropped, so the frontend can render "This question has
        # since been removed" without the rest of the attempt's questions
        # shifting position or its score being affected (score_percent was
        # already computed and stored at submission time, never recomputed).
        questions_by_id = LevelQuestion.objects.filter(id__in=obj.questions_drawn).prefetch_related('choices').in_bulk()
        ordered = []
        for question_id in obj.questions_drawn:
            question = questions_by_id.get(question_id)
            if question is None:
                ordered.append({
                    'id': question_id, 'question_text': '', 'question_type': '', 'marks': 0,
                    'choices': [], 'removed': True,
                })
            else:
                data = LevelQuestionSerializer(question, context=self.context).data
                data['removed'] = False
                ordered.append(data)
        return ordered


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


class LevelAssessmentAdvanceSerializer(serializers.Serializer):
    """Input for LevelAssessmentAttemptViewSet.advance — see
    levelassessments.services.advance_level_assessment_attempt for the
    sequential-only validation this hands off to."""

    current_question_index = serializers.IntegerField(min_value=0)


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
