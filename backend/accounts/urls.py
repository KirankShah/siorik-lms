from rest_framework_simplejwt.views import TokenRefreshView

from django.urls import path

from .views import MeView, ThrottledTokenObtainPairView

urlpatterns = [
    path('login/', ThrottledTokenObtainPairView.as_view(), name='auth-login'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
]
