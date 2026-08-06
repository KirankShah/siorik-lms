from rest_framework_simplejwt.views import TokenRefreshView

from django.urls import path

from .views import MeView, SetPasswordView, ThrottledTokenObtainPairView

urlpatterns = [
    path('login/', ThrottledTokenObtainPairView.as_view(), name='auth-login'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('set-password/', SetPasswordView.as_view(), name='auth-set-password'),
]
