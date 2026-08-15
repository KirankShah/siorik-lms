from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsAdminRole

from .models import Character, Scene
from .serializers import CharacterSerializer, SceneSerializer


class CharacterViewSet(viewsets.ReadOnlyModelViewSet):
    """The curated set of Dialogue-element characters. Read-only — the roster is
    loaded via the Django admin once the illustration pack is sourced, not
    created through this API — and restricted to admin roles since only
    course authors need to browse it (to pick characters for a Dialogue
    element), not learners.
    """

    queryset = Character.objects.all()
    serializer_class = CharacterSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]


class SceneViewSet(viewsets.ReadOnlyModelViewSet):
    """Same shape as CharacterViewSet — see its docstring."""

    queryset = Scene.objects.all()
    serializer_class = SceneSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
