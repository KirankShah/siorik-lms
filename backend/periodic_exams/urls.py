from django.urls import path

from .views import (
    AvailabilityView,
    PlatformOrganizationListView,
    PlatformOrganizationToggleView,
    ReadinessView,
    SettingsView,
)

urlpatterns = [
    path('availability/', AvailabilityView.as_view(), name='periodic-exam-availability'),
    path('readiness/', ReadinessView.as_view(), name='periodic-exam-readiness'),
    path('settings/', SettingsView.as_view(), name='periodic-exam-settings'),
    path('platform/organizations/', PlatformOrganizationListView.as_view(), name='periodic-exam-platform-organizations'),
    path(
        'platform/organizations/<int:organization_id>/',
        PlatformOrganizationToggleView.as_view(),
        name='periodic-exam-platform-toggle',
    ),
]
