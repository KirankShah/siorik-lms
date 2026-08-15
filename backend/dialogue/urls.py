from rest_framework.routers import DefaultRouter

from .views import CharacterViewSet, SceneViewSet

router = DefaultRouter()
router.register('characters', CharacterViewSet, basename='character')
router.register('scenes', SceneViewSet, basename='scene')

urlpatterns = router.urls
