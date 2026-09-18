import os

from django.core.files.base import ContentFile
from django.db import models, transaction

from .models import Course, Element, Lesson, Module, Slide


def _unique_course_slug(base_slug):
    """Disambiguate base_slug against existing Course.slug rows, same
    suffix-on-collision pattern as accounts.serializers.OrganizationSerializer."""
    slug = base_slug
    suffix = 2
    while Course.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{suffix}'
        suffix += 1
    return slug


def _deep_copy_file(target, field_name, source_field):
    """
    Copies source_field's actual bytes onto target.<field_name> as a brand
    new storage object (new key/path), then saves target. Used everywhere
    clone_course/copy_lesson touch a File/ImageField.

    Passing a source FieldFile straight into .objects.create() (the bug this
    fixes) only copies its `name` — the storage path string — never its
    bytes, so the "clone" ends up pointing at the exact same physical file as
    the source. Two rows (a platform master and an org's clone, or two
    different orgs' clones) then silently share one object: deleting or
    overwriting it for one side changes or breaks it for the other, with no
    error until playback. This always re-uploads the bytes under a fresh
    storage key instead, so the copy is genuinely independent.

    `target` must already be saved (have a pk). A no-op when source_field is
    empty (blank/null FileField) — there is nothing to copy.
    """
    if not source_field:
        return
    source_field.open('rb')
    try:
        content = ContentFile(source_field.read())
    finally:
        source_field.close()
    getattr(target, field_name).save(os.path.basename(source_field.name), content, save=True)


def _clone_quiz_slide(source_slide, cloned_slide):
    from assessments.models import CategorizeItem, CategoryBucket, Choice, HotspotRegion, Question, Quiz, WordBankToken

    quiz = source_slide.quizzes.first()
    if quiz is None:
        return

    cloned_quiz = Quiz.objects.create(
        slide=cloned_slide,
        title=quiz.title,
        pass_percentage=quiz.pass_percentage,
        time_limit_minutes=quiz.time_limit_minutes,
        max_attempts=quiz.max_attempts,
        randomize_questions=quiz.randomize_questions,
    )

    for question in quiz.questions.order_by('order'):
        cloned_question = Question.objects.create(
            quiz=cloned_quiz,
            question_text=question.question_text,
            order=question.order,
            marks=question.marks,
            explanation=question.explanation,
            feedback_correct=question.feedback_correct,
            feedback_incorrect=question.feedback_incorrect,
            question_type=question.question_type,
            fill_blank_mode=question.fill_blank_mode,
            points=question.points,
            video_url=question.video_url,
        )
        _deep_copy_file(cloned_question, 'image', question.image)

        bucket_map = {}
        for bucket in question.buckets.order_by('order'):
            bucket_map[bucket.id] = CategoryBucket.objects.create(
                question=cloned_question, label=bucket.label, order=bucket.order
            )

        for choice in question.choices.order_by('order'):
            Choice.objects.create(
                question=cloned_question,
                choice_text=choice.choice_text,
                is_correct=choice.is_correct,
                order=choice.order,
                match_text=choice.match_text,
                blank_index=choice.blank_index,
            )

        for token in question.word_bank_tokens.order_by('order'):
            WordBankToken.objects.create(
                question=cloned_question,
                text=token.text,
                correct_blank_index=token.correct_blank_index,
                order=token.order,
            )

        for item in question.categorize_items.order_by('order'):
            cloned_item = CategorizeItem.objects.create(
                question=cloned_question,
                item_text=item.item_text,
                correct_bucket=bucket_map[item.correct_bucket_id],
                order=item.order,
            )
            _deep_copy_file(cloned_item, 'item_image', item.item_image)

        for region in question.hotspot_regions.all():
            HotspotRegion.objects.create(
                question=cloned_question,
                x=region.x,
                y=region.y,
                width=region.width,
                height=region.height,
                is_correct=region.is_correct,
            )


def _clone_assignment_slide(source_slide, cloned_slide):
    from assignments.models import Assignment

    assignment = getattr(source_slide, 'assignment', None)
    if assignment is None:
        return

    Assignment.objects.create(
        slide=cloned_slide,
        instructions=assignment.instructions,
        submission_type=assignment.submission_type,
        max_marks=assignment.max_marks,
        due_offset_days=assignment.due_offset_days,
    )


def _clone_scenario_slide(source_slide, cloned_slide):
    from scenarios.models import ScenarioChoice, ScenarioNode

    nodes = list(source_slide.scenario_nodes.all())
    node_map = {}
    for node in nodes:
        cloned_node = ScenarioNode.objects.create(
            slide=cloned_slide,
            node_key=node.node_key,
            prompt=node.prompt,
            is_start=node.is_start,
        )
        _deep_copy_file(cloned_node, 'prompt_image', node.prompt_image)
        node_map[node.id] = cloned_node

    for node in nodes:
        for choice in node.choices.order_by('order'):
            ScenarioChoice.objects.create(
                node=node_map[node.id],
                choice_text=choice.choice_text,
                next_node=node_map.get(choice.next_node_id),
                feedback_text=choice.feedback_text,
                is_recommended=choice.is_recommended,
                order=choice.order,
            )


_SLIDE_CLONERS = {
    Slide.SlideType.QUIZ: _clone_quiz_slide,
    Slide.SlideType.ASSIGNMENT: _clone_assignment_slide,
    Slide.SlideType.SCENARIO: _clone_scenario_slide,
}


@transaction.atomic
def copy_lesson(source_lesson, target_module, *, order=None):
    """
    Deep-copies a single Lesson (and its Slides/Elements/Quiz/Assignment/
    Scenario/Narration content) into target_module, appending it after that
    module's existing lessons unless `order` is given.

    Used to backfill a lesson added to a platform master course into course
    clones that were already forked from it (Course.cloned_from) — clone_course
    only runs once at fork time and deliberately never re-syncs, so new lessons
    added afterward need this to reach existing clones. clone_course itself
    calls this once per lesson rather than duplicating this logic.

    Every File/ImageField touched here (Lesson.content_file,
    SlideNarration.audio_file, Element.file/video_file, and — via
    _SLIDE_CLONERS — Question.image/CategorizeItem.item_image/
    ScenarioNode.prompt_image) is deep-copied via _deep_copy_file: the new
    row gets its own independent storage object, never a reference to the
    source's file. dialogue_scene/dialogue_character_left/right are the one
    deliberate exception — those FKs point at the shared, platform-wide
    illustration library (dialogue.Scene/Character), not per-course content,
    so copying the reference itself is correct there.
    """
    from narration.models import SlideNarration

    if order is None:
        last_order = target_module.lessons.aggregate(models.Max('order'))['order__max'] or 0
        order = last_order + 1

    cloned_lesson = Lesson.objects.create(
        module=target_module,
        title=source_lesson.title,
        lesson_type=source_lesson.lesson_type,
        content_url=source_lesson.content_url,
        order=order,
        estimated_minutes=source_lesson.estimated_minutes,
    )
    _deep_copy_file(cloned_lesson, 'content_file', source_lesson.content_file)

    for slide in source_lesson.slides.order_by('order'):
        cloned_slide = Slide.objects.create(
            lesson=cloned_lesson,
            title=slide.title,
            order=slide.order,
            slide_type=slide.slide_type,
            layout=slide.layout,
            image_column_width=slide.image_column_width,
            template_override=slide.template_override,
            estimated_minutes=slide.estimated_minutes,
        )

        for narration in slide.narrations.all():
            cloned_narration = SlideNarration.objects.create(
                slide=cloned_slide,
                language=narration.language,
                script_text=narration.script_text,
                voice_name=narration.voice_name,
                generated_by=narration.generated_by,
            )
            _deep_copy_file(cloned_narration, 'audio_file', narration.audio_file)

        if slide.slide_type == Slide.SlideType.CONTENT:
            for element in slide.elements.order_by('order'):
                cloned_element = Element.objects.create(
                    slide=cloned_slide,
                    order=element.order,
                    element_type=element.element_type,
                    rich_text=element.rich_text,
                    video_url=element.video_url,
                    embed_url=element.embed_url,
                    caption=element.caption,
                    align=element.align,
                    dialogue_scene=element.dialogue_scene,
                    dialogue_character_left=element.dialogue_character_left,
                    dialogue_character_right=element.dialogue_character_right,
                    dialogue_lines=element.dialogue_lines,
                )
                _deep_copy_file(cloned_element, 'file', element.file)
                _deep_copy_file(cloned_element, 'video_file', element.video_file)
        else:
            cloner = _SLIDE_CLONERS.get(slide.slide_type)
            if cloner:
                cloner(slide, cloned_slide)

    return cloned_lesson


@transaction.atomic
def clone_course(source_course, created_by, *, organization=None, title=None, slug_seed=None):
    """
    Deep-copies source_course into a brand new, independent course. The clone
    is a one-time fork: nothing links it back to the source beyond the
    informational Course.cloned_from FK, and no learner-generated data
    (enrollments, attempts, submissions, certificates, SlideRevision history)
    is ever copied — see the plan this implements for the full rationale.
    SlideNarration IS copied (script text, audio file, voice) since it's
    admin-authored content tied to the slide's text, not learner data —
    otherwise every clone would silently start with zero narration. See
    copy_lesson's own docstring (used here per-lesson) for exactly which
    fields are deep-copied into independent files vs. left as a shared FK.

    Ownership of the copy follows `organization`:

    - `organization` given -> an ORGANIZATION-owned copy for that org (a
      platform course forked for self-serve editing, or an org course
      duplicated in place for the same org).
    - `organization` None -> a PLATFORM-owned copy (an org course pulled up
      into the platform library, or a platform course duplicated in place) —
      platform-admin only, enforced by the caller.

    `title` overrides the copy's title (defaults to the source's). `slug_seed`
    overrides the base slug that gets disambiguated against existing courses.
    """
    if organization is not None:
        content_owner = Course.ContentOwner.ORGANIZATION
        default_slug_seed = f'{source_course.slug}-{organization.slug}'
    else:
        content_owner = Course.ContentOwner.PLATFORM
        default_slug_seed = f'{source_course.slug}-platform'

    cloned_course = Course.objects.create(
        title=title or source_course.title,
        slug=_unique_course_slug(slug_seed or default_slug_seed),
        description=source_course.description,
        organization=organization,
        content_owner=content_owner,
        is_published=False,
        template=source_course.template,
        certificate_expiry_months=source_course.certificate_expiry_months,
        certificate_template=None,
        completion_deadline_days=source_course.completion_deadline_days,
        is_demo_available=False,
        created_by=created_by,
        cloned_from=source_course,
    )
    _deep_copy_file(cloned_course, 'cover_image', source_course.cover_image)

    for module in source_course.modules.order_by('order'):
        cloned_module = Module.objects.create(course=cloned_course, title=module.title, order=module.order)

        # Reuses copy_lesson (rather than re-implementing the same
        # Lesson/Slide/Narration/Element/quiz/assignment/scenario copy shape
        # a second time here) so the two never drift out of sync — the exact
        # divergence that let this function's file-copying bug go unfixed in
        # one of the two for a while. order=lesson.order preserves each
        # lesson's exact original position instead of copy_lesson's own
        # append-to-the-end default.
        for lesson in module.lessons.order_by('order'):
            copy_lesson(lesson, cloned_module, order=lesson.order)

    return cloned_course
