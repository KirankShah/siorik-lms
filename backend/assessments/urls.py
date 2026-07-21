from rest_framework.routers import DefaultRouter

from .views import ChoiceViewSet, QuestionViewSet, QuizViewSet

router = DefaultRouter()
router.register('quizzes', QuizViewSet, basename='quiz')
router.register('questions', QuestionViewSet, basename='question')
router.register('choices', ChoiceViewSet, basename='choice')

urlpatterns = router.urls
