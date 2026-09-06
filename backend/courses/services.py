from django.db import transaction

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
            image=question.image,
            video_url=question.video_url,
        )

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
            CategorizeItem.objects.create(
                question=cloned_question,
                item_text=item.item_text,
                item_image=item.item_image,
                correct_bucket=bucket_map[item.correct_bucket_id],
                order=item.order,
            )

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
    node_map = {
        node.id: ScenarioNode.objects.create(
            slide=cloned_slide,
            node_key=node.node_key,
            prompt=node.prompt,
            prompt_image=node.prompt_image,
            is_start=node.is_start,
        )
        for node in nodes
    }

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
def clone_course_for_organization(source_course, organization, created_by):
    """
    Deep-copies source_course (expected PLATFORM-owned) into a brand new,
    independent ORGANIZATION-owned course for `organization`. The clone is a
    one-time fork: nothing links it back to the source beyond the
    informational Course.cloned_from FK, and no learner-generated data
    (enrollments, attempts, submissions, certificates, SlideRevision history)
    is ever copied — see the plan this implements for the full rationale.
    """
    cloned_course = Course.objects.create(
        title=source_course.title,
        slug=_unique_course_slug(f'{source_course.slug}-{organization.slug}'),
        description=source_course.description,
        organization=organization,
        content_owner=Course.ContentOwner.ORGANIZATION,
        cover_image=source_course.cover_image,
        is_published=False,
        template=source_course.template,
        certificate_pass_threshold=source_course.certificate_pass_threshold,
        certificate_expiry_months=source_course.certificate_expiry_months,
        certificate_template=None,
        completion_deadline_days=source_course.completion_deadline_days,
        is_demo_available=False,
        created_by=created_by,
        cloned_from=source_course,
    )

    for module in source_course.modules.order_by('order'):
        cloned_module = Module.objects.create(course=cloned_course, title=module.title, order=module.order)

        for lesson in module.lessons.order_by('order'):
            cloned_lesson = Lesson.objects.create(
                module=cloned_module,
                title=lesson.title,
                lesson_type=lesson.lesson_type,
                content_file=lesson.content_file,
                content_url=lesson.content_url,
                order=lesson.order,
                estimated_minutes=lesson.estimated_minutes,
            )

            for slide in lesson.slides.order_by('order'):
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

                if slide.slide_type == Slide.SlideType.CONTENT:
                    for element in slide.elements.order_by('order'):
                        Element.objects.create(
                            slide=cloned_slide,
                            order=element.order,
                            element_type=element.element_type,
                            rich_text=element.rich_text,
                            file=element.file,
                            video_url=element.video_url,
                            video_file=element.video_file,
                            embed_url=element.embed_url,
                            caption=element.caption,
                            align=element.align,
                            dialogue_scene=element.dialogue_scene,
                            dialogue_character_left=element.dialogue_character_left,
                            dialogue_character_right=element.dialogue_character_right,
                            dialogue_lines=element.dialogue_lines,
                        )
                else:
                    cloner = _SLIDE_CLONERS.get(slide.slide_type)
                    if cloner:
                        cloner(slide, cloned_slide)

    return cloned_course
