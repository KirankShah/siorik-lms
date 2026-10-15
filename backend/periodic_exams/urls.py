from django.urls import path

from .views import (
    AvailabilityView,
    LearnerAdvanceView,
    LearnerAttemptStartView,
    LearnerAttemptView,
    LearnerCurrentAnswerView,
    LearnerResultView,
    LearnerSubmitView,
    LearnerSummaryView,
    PlatformOrganizationListView,
    PlatformOrganizationToggleView,
    ReadinessView,
    SettingsView,
)

urlpatterns = [
    path('availability/', AvailabilityView.as_view(), name='periodic-exam-availability'),
    path('readiness/', ReadinessView.as_view(), name='periodic-exam-readiness'),
    path('me/summary/', LearnerSummaryView.as_view(), name='periodic-exam-learner-summary'),
    path('me/attempts/start/', LearnerAttemptStartView.as_view(), name='periodic-exam-attempt-start'),
    path('me/attempts/<int:attempt_id>/', LearnerAttemptView.as_view(), name='periodic-exam-attempt'),
    path(
        'me/attempts/<int:attempt_id>/current-answer/',
        LearnerCurrentAnswerView.as_view(),
        name='periodic-exam-current-answer',
    ),
    path(
        'me/attempts/<int:attempt_id>/advance/',
        LearnerAdvanceView.as_view(),
        name='periodic-exam-advance',
    ),
    path(
        'me/attempts/<int:attempt_id>/submit/',
        LearnerSubmitView.as_view(),
        name='periodic-exam-submit',
    ),
    path(
        'me/attempts/<int:attempt_id>/result/',
        LearnerResultView.as_view(),
        name='periodic-exam-result',
    ),
    path('settings/', SettingsView.as_view(), name='periodic-exam-settings'),
    path('platform/organizations/', PlatformOrganizationListView.as_view(), name='periodic-exam-platform-organizations'),
    path(
        'platform/organizations/<int:organization_id>/',
        PlatformOrganizationToggleView.as_view(),
        name='periodic-exam-platform-toggle',
    ),
]
