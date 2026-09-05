from rest_framework.routers import DefaultRouter

from .views import SlideNarrationViewSet

router = DefaultRouter()
router.register('slide-narrations', SlideNarrationViewSet, basename='slide-narration')

urlpatterns = router.urls
