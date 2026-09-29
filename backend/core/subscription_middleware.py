from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.authentication import JWTAuthentication


class SubscriptionAccessMiddleware:
    """One API-wide subscription gate, applied after authentication.

    Login, token refresh, and the current-user endpoint stay available so an
    expired tenant user can authenticate successfully and the SPA can render
    the dedicated expiry screen. Platform admins are explicitly ignored by
    OrganizationSettings.is_access_locked_for().
    """

    EXEMPT_PATHS = {
        '/api/auth/login/',
        '/api/auth/refresh/',
        '/api/auth/me/',
        '/api/auth/password-reset/',
        '/api/auth/password-reset-confirm/',
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_authentication = JWTAuthentication()

    def __call__(self, request):
        if request.path.startswith('/api/') and request.path not in self.EXEMPT_PATHS:
            user = request.user if getattr(request.user, 'is_authenticated', False) else None
            if user is None:
                try:
                    authenticated = self.jwt_authentication.authenticate(request)
                except (AuthenticationFailed, InvalidToken, TokenError):
                    authenticated = None  # Let DRF return its normal auth error.
                if authenticated is not None:
                    user = authenticated[0]

            if user is not None and user.organization_id is not None:
                if user.organization.settings.is_access_locked_for(user):
                    return JsonResponse(
                        {
                            'detail': "Your organization's subscription has expired.",
                            'code': 'subscription_expired',
                        },
                        status=403,
                    )

        return self.get_response(request)
