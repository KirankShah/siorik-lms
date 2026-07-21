from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.urls import path

from .views import MeView

urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='auth-login'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
]
