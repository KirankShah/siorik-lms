from rest_framework.routers import DefaultRouter

from .views import ChoiceViewSet, QuestionViewSet, QuizAnswerGradingViewSet, QuizViewSet

router = DefaultRouter()
router.register('quizzes', QuizViewSet, basename='quiz')
router.register('questions', QuestionViewSet, basename='question')
router.register('choices', ChoiceViewSet, basename='choice')
router.register('quiz-answers', QuizAnswerGradingViewSet, basename='quiz-answer-grading')

urlpatterns = router.urls
