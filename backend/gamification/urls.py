from rest_framework.routers import DefaultRouter

from .views import BadgeViewSet, LeaderboardEntryViewSet, UserBadgeViewSet

router = DefaultRouter()
router.register('leaderboard', LeaderboardEntryViewSet, basename='leaderboard')
router.register('badges', BadgeViewSet, basename='badge')
router.register('user-badges', UserBadgeViewSet, basename='user-badge')

urlpatterns = router.urls
