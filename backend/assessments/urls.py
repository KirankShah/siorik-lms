from rest_framework.routers import DefaultRouter

from .views import (
    CategorizeItemViewSet,
    CategoryBucketViewSet,
    ChoiceViewSet,
    HotspotRegionViewSet,
    QuestionViewSet,
    QuizAnswerGradingViewSet,
    QuizViewSet,
)

router = DefaultRouter()
router.register('quizzes', QuizViewSet, basename='quiz')
router.register('questions', QuestionViewSet, basename='question')
router.register('choices', ChoiceViewSet, basename='choice')
router.register('category-buckets', CategoryBucketViewSet, basename='category-bucket')
router.register('categorize-items', CategorizeItemViewSet, basename='categorize-item')
router.register('hotspot-regions', HotspotRegionViewSet, basename='hotspot-region')
router.register('quiz-answers', QuizAnswerGradingViewSet, basename='quiz-answer-grading')

urlpatterns = router.urls
