from rest_framework.routers import DefaultRouter

from .views import ScenarioAttemptViewSet, ScenarioChoiceViewSet, ScenarioNodeViewSet

router = DefaultRouter()
router.register('scenario-nodes', ScenarioNodeViewSet, basename='scenario-node')
router.register('scenario-choices', ScenarioChoiceViewSet, basename='scenario-choice')
router.register('scenario-attempts', ScenarioAttemptViewSet, basename='scenario-attempt')

urlpatterns = router.urls
