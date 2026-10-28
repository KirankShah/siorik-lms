from django.urls import path

from .views import (
    AvailabilityView,
    LearnerAdvanceView,
    LearnerAttemptStartView,
    LearnerHistoryView,
    LearnerAttemptView,
    LearnerCurrentAnswerView,
    LearnerResultView,
    LearnerSubmitView,
    LearnerSummaryView,
    PlatformOrganizationListView,
    PlatformOrganizationToggleView,
    ReadinessView,
    ReportCycleListView,
    ReportHistoryView,
    ReportView,
    SettingsView,
)

urlpatterns = [
    path('availability/', AvailabilityView.as_view(), name='periodic-exam-availability'),
    path('readiness/', ReadinessView.as_view(), name='periodic-exam-readiness'),
    path('report/cycles/', ReportCycleListView.as_view(), name='periodic-exam-report-cycles'),
    path('report/history/', ReportHistoryView.as_view(), name='periodic-exam-report-history'),
    path('report/history.csv', ReportHistoryView.as_view(), {'export_format': 'csv'}, name='periodic-exam-report-history-csv'),
    path('report/history.xlsx', ReportHistoryView.as_view(), {'export_format': 'xlsx'}, name='periodic-exam-report-history-xlsx'),
    path('report/cycles/<int:cycle_id>/', ReportView.as_view(), name='periodic-exam-report'),
    path('report/cycles/<int:cycle_id>.csv', ReportView.as_view(), {'export_format': 'csv'}, name='periodic-exam-report-csv'),
    path('report/cycles/<int:cycle_id>.xlsx', ReportView.as_view(), {'export_format': 'xlsx'}, name='periodic-exam-report-xlsx'),
    path('me/summary/', LearnerSummaryView.as_view(), name='periodic-exam-learner-summary'),
    path('me/history/', LearnerHistoryView.as_view(), name='periodic-exam-learner-history'),
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
