from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.permissions import IsAdminRole
from courses.permissions import editable_courses_for_user, exclude_demo_locked, visible_courses_for_user
from gamification.services import update_gamification_for_user

from .models import (
    CategorizeItem,
    CategoryBucket,
    Choice,
    HotspotRegion,
    Question,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    WordBankToken,
)
from .serializers import (
    CategorizeItemWriteSerializer,
    CategoryBucketWriteSerializer,
    ChoiceWriteSerializer,
    HotspotRegionWriteSerializer,
    QuestionWriteSerializer,
    QuizAnswerGradingSerializer,
    QuizAttemptSerializer,
    QuizSerializer,
    QuizSubmitSerializer,
    QuizWriteSerializer,
    WordBankTokenWriteSerializer,
)

WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')


class QuizViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Quiz.objects.select_related('slide__lesson__module__course').prefetch_related(
        'questions__choices',
        'questions__buckets',
        'questions__categorize_items',
        'questions__hotspot_regions',
        'questions__word_bank_tokens',
    )
    throttle_scope = None  # overridden per-action to 'quiz-submit' on the submit() action below

    def get_permissions(self):
        if self.action in WRITE_ACTIONS:
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        slide_id = self.request.query_params.get('slide')
        # A `slide`-filtered lookup is how the learner-facing player resolves
        # "the quiz for this slide", so it's scoped to visible (not just
        # editable) courses — same as retrieve/submit. The unfiltered list
        # (the admin Assessments page) stays editable-only.
        if self.action in ('retrieve', 'submit') or slide_id:
            queryset = super().get_queryset().filter(
                slide__lesson__module__course__in=visible_courses_for_user(self.request.user)
            )
            queryset = exclude_demo_locked(queryset, self.request.user, 'slide__lesson')
        else:
            queryset = super().get_queryset().filter(
                slide__lesson__module__course__in=editable_courses_for_user(self.request.user)
            )
        if slide_id:
            queryset = queryset.filter(slide_id=slide_id)
        return queryset

    def get_serializer_class(self):
        if self.action in WRITE_ACTIONS:
            return QuizWriteSerializer
        return QuizSerializer

    def perform_create(self, serializer):
        slide = serializer.validated_data['slide']
        course = slide.lesson.module.course
        if not editable_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'slide': 'You do not have permission to modify this course.'})
        serializer.save()

    @action(detail=True, methods=['post'], throttle_classes=[ScopedRateThrottle], throttle_scope='quiz-submit')
    def submit(self, request, pk=None):
        quiz = self.get_object()

        attempts_taken = QuizAttempt.objects.filter(user=request.user, quiz=quiz).count()
        if quiz.max_attempts is not None and attempts_taken >= quiz.max_attempts:
            return Response({'detail': 'Maximum number of attempts reached.'}, status=400)

        serializer = QuizSubmitSerializer(data=request.data, context={'quiz': quiz})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            attempt = QuizAttempt.objects.create(
                user=request.user,
                quiz=quiz,
                attempt_number=attempts_taken + 1,
            )
            for answer_data in serializer.validated_data['answers']:
                question = answer_data['question']
                selected_choices = answer_data['selected_choices']
                category_placements = {}
                fill_blank_text = {}
                word_bank_placements = {}

                if question.question_type == Question.QuestionType.ORDERING:
                    # Set equality (below) discards position entirely, which
                    # is exactly the information ORDERING needs graded, so it
                    # gets its own comparison: the learner's submission must
                    # be the choices in the exact order they were dragged
                    # into (PrimaryKeyRelatedField(many=True) preserves the
                    # submitted list order), matching the true order 1:1.
                    correct_sequence = list(question.choices.order_by('order', 'id').values_list('id', flat=True))
                    submitted_sequence = [choice.id for choice in selected_choices]
                    is_correct = submitted_sequence == correct_sequence
                elif question.question_type == Question.QuestionType.CATEGORIZE:
                    # Neither a set nor a sequence — each item has exactly one
                    # correct bucket, so this compares the full item->bucket
                    # mapping. All-or-nothing, same spirit as MULTIPLE_ANSWER:
                    # every item must land in its correct bucket.
                    category_placements = {
                        placement['item'].id: placement['bucket'].id
                        for placement in answer_data['category_placements']
                    }
                    correct_placements = {
                        item.id: item.correct_bucket_id for item in question.categorize_items.all()
                    }
                    is_correct = category_placements == correct_placements
                elif question.question_type == Question.QuestionType.HOTSPOT:
                    # Same all-or-nothing set equality as the default branch
                    # below, just against HotspotRegion instead of Choice —
                    # every correct region must be picked and no incorrect
                    # one, same spirit as MULTIPLE_ANSWER/CATEGORIZE.
                    correct_region_ids = set(
                        question.hotspot_regions.filter(is_correct=True).values_list('id', flat=True)
                    )
                    selected_region_ids = {region.id for region in answer_data['selected_regions']}
                    is_correct = selected_region_ids == correct_region_ids
                elif question.question_type == Question.QuestionType.FILL_BLANK:
                    if question.fill_blank_mode == Question.FillBlankMode.WORD_BANK:
                        # Each blank has exactly one correct token — an
                        # all-or-nothing mapping comparison, same spirit as
                        # CATEGORIZE.
                        word_bank_placements = {
                            placement['blank_index']: placement['token'].id
                            for placement in answer_data['word_bank_placements']
                        }
                        correct_word_bank = {
                            token.correct_blank_index: token.id
                            for token in question.word_bank_tokens.all()
                            if token.correct_blank_index is not None
                        }
                        is_correct = bool(correct_word_bank) and word_bank_placements == correct_word_bank
                    else:
                        # TEXT_INPUT: each blank accepts any of its own set
                        # of accepted answers (Choice rows sharing that
                        # blank_index), matched case-insensitively. Every
                        # blank must match — no partial credit, same as
                        # every other multi-part type here.
                        accepted_by_blank = {}
                        for choice in question.choices.all():
                            blank_index = choice.blank_index or 1
                            accepted_by_blank.setdefault(blank_index, set()).add(choice.choice_text.strip().casefold())
                        submitted_text = answer_data['fill_blank_text']
                        is_correct = bool(accepted_by_blank) and all(
                            submitted_text.get(str(blank_index), '').strip().casefold() in accepted
                            for blank_index, accepted in accepted_by_blank.items()
                        )
                        fill_blank_text = dict(submitted_text)
                else:
                    correct_choice_ids = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
                    selected_ids = {choice.id for choice in selected_choices}

                    # Exact set equality gives all-or-nothing scoring for
                    # every other question type: SINGLE_CHOICE/TRUE_FALSE
                    # just happen to have a one-element correct set, while
                    # MULTIPLE_ANSWER's correct set can have several, and
                    # MATCHING's frontend only includes a choice id once it's
                    # confirmed that pair was placed correctly. Either way,
                    # the learner must select every correct option and no
                    # incorrect one to be marked correct — no partial credit
                    # by default. (Partial-credit scoring would be a
                    # reasonable future enhancement, but is out of scope
                    # here.)
                    is_correct = selected_ids == correct_choice_ids

                quiz_answer = QuizAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    is_correct=is_correct,
                    category_placements=category_placements,
                    fill_blank_text=fill_blank_text,
                    word_bank_placements=word_bank_placements,
                )
                quiz_answer.selected_choices.set(selected_choices)
                quiz_answer.selected_regions.set(answer_data['selected_regions'])

            attempt.calculate_score_percent()
            update_gamification_for_user(request.user)

        return Response(QuizAttemptSerializer(attempt).data, status=201)


class QuestionViewSet(viewsets.ModelViewSet):
    serializer_class = QuestionWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return Question.objects.filter(
            quiz__slide__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        quiz = serializer.validated_data['quiz']
        course_id = quiz.slide.lesson.module.course_id
        if not editable_courses_for_user(self.request.user).filter(pk=course_id).exists():
            raise ValidationError({'quiz': 'You do not have permission to modify this quiz.'})
        serializer.save()


class ChoiceViewSet(viewsets.ModelViewSet):
    serializer_class = ChoiceWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return Choice.objects.filter(
            question__quiz__slide__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        question = serializer.validated_data['question']
        course_id = question.quiz.slide.lesson.module.course_id
        if not editable_courses_for_user(self.request.user).filter(pk=course_id).exists():
            raise ValidationError({'question': 'You do not have permission to modify this question.'})
        serializer.save()


class CategoryBucketViewSet(viewsets.ModelViewSet):
    serializer_class = CategoryBucketWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return CategoryBucket.objects.filter(
            question__quiz__slide__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        question = serializer.validated_data['question']
        course_id = question.quiz.slide.lesson.module.course_id
        if not editable_courses_for_user(self.request.user).filter(pk=course_id).exists():
            raise ValidationError({'question': 'You do not have permission to modify this question.'})
        serializer.save()


class CategorizeItemViewSet(viewsets.ModelViewSet):
    serializer_class = CategorizeItemWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return CategorizeItem.objects.filter(
            question__quiz__slide__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        question = serializer.validated_data['question']
        course_id = question.quiz.slide.lesson.module.course_id
        if not editable_courses_for_user(self.request.user).filter(pk=course_id).exists():
            raise ValidationError({'question': 'You do not have permission to modify this question.'})
        serializer.save()


class HotspotRegionViewSet(viewsets.ModelViewSet):
    serializer_class = HotspotRegionWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return HotspotRegion.objects.filter(
            question__quiz__slide__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        question = serializer.validated_data['question']
        course_id = question.quiz.slide.lesson.module.course_id
        if not editable_courses_for_user(self.request.user).filter(pk=course_id).exists():
            raise ValidationError({'question': 'You do not have permission to modify this question.'})
        serializer.save()


class WordBankTokenViewSet(viewsets.ModelViewSet):
    serializer_class = WordBankTokenWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return WordBankToken.objects.filter(
            question__quiz__slide__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        question = serializer.validated_data['question']
        course_id = question.quiz.slide.lesson.module.course_id
        if not editable_courses_for_user(self.request.user).filter(pk=course_id).exists():
            raise ValidationError({'question': 'You do not have permission to modify this question.'})
        serializer.save()


class QuizAnswerGradingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Instructor grading queue for SHORT_ANSWER/ESSAY answers — list + grade only."""

    serializer_class = QuizAnswerGradingSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        queryset = QuizAnswer.objects.filter(
            question__question_type__in=[Question.QuestionType.SHORT_ANSWER, Question.QuestionType.ESSAY],
            question__quiz__slide__lesson__module__course__in=editable_courses_for_user(self.request.user),
        ).select_related('question', 'attempt', 'attempt__user', 'attempt__quiz')
        if self.request.query_params.get('ungraded') == 'true':
            queryset = queryset.filter(marks_awarded__isnull=True)
        return queryset

    def perform_update(self, serializer):
        serializer.save(graded_at=timezone.now())
