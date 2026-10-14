import logging
import uuid

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsPlatformAdminRole
from courses.models import Slide
from courses.permissions import path_accessible_courses_for_user

from .models import SlideNarration
from .serializers import SlideNarrationSerializer
from .services import NarrationGenerationError, generate_slide_narration

logger = logging.getLogger(__name__)


class SlideNarrationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only for any authenticated user who can see the slide's course (the
    learner-facing player resolves narration for their preferred language the
    same way it resolves an assignment/quiz — GET ?slide=<id>). Generation is
    the only write path, and is restricted to PLATFORM_ADMIN — enforced here
    server-side via get_permissions, not just hidden in the authoring UI.
    """

    serializer_class = SlideNarrationSerializer

    def get_permissions(self):
        if self.action == 'generate':
            return [IsAuthenticated(), IsPlatformAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = SlideNarration.objects.filter(
            slide__lesson__module__course__in=path_accessible_courses_for_user(self.request.user)
        )
        slide_id = self.request.query_params.get('slide')
        if slide_id:
            queryset = queryset.filter(slide_id=slide_id)
        return queryset

    @action(detail=False, methods=['post'])
    def generate(self, request):
        slide_id = request.data.get('slide')
        language = request.data.get('language')

        if language not in SlideNarration.Language.values:
            raise ValidationError({'language': f'Must be one of: {", ".join(SlideNarration.Language.values)}.'})

        try:
            slide = Slide.objects.get(pk=slide_id)
        except (Slide.DoesNotExist, ValueError, TypeError):
            raise ValidationError({'slide': 'Slide not found.'})

        # Every failure gets a short reference that appears both in the admin
        # message and beside the full traceback in the narration log, so a
        # reported failure can always be traced. Unexpected exceptions still
        # return JSON rather than Django's HTML 500 page, which the authoring
        # UI cannot read.
        try:
            narration = generate_slide_narration(slide=slide, language=language, user=request.user)
        except NarrationGenerationError as exc:
            reference = uuid.uuid4().hex[:8]
            logger.warning(
                'Narration generation failed for slide %s (%s) [ref %s]: %s',
                slide.id, language, reference, exc, exc_info=exc.__cause__ is not None,
            )
            raise ValidationError({'detail': f'{exc} (Reference: {reference})', 'reference': reference})
        except Exception:
            reference = uuid.uuid4().hex[:8]
            logger.exception('Unexpected narration generation failure for slide %s (%s) [ref %s]', slide.id, language, reference)
            return Response(
                {'detail': f'Narration generation failed on the server. Reference: {reference}.', 'reference': reference},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(SlideNarrationSerializer(narration).data)
