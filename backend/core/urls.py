"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as serve_static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('certificates.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('accounts.api_urls')),
    path('api/', include('courses.urls')),
    path('api/', include('assessments.urls')),
    path('api/', include('assignments.urls')),
    path('api/', include('scenarios.urls')),
    path('api/', include('gamification.urls')),
    path('api/', include('certificates.api_urls')),
    path('api/', include('dialogue.urls')),
    path('api/', include('narration.urls')),
]

# Not gated on DEBUG: with USE_S3=False, this is the only thing that serves
# uploaded files (course covers, certificates, lesson attachments, question
# images, ...) in production too, since there's no separate Apache/LiteSpeed
# vhost rule serving MEDIA_ROOT directly. Deliberately NOT using
# django.conf.urls.static.static() here — that helper has `if not
# settings.DEBUG: return []` hardcoded into its own implementation, so it
# silently produces zero URL patterns in production regardless of how it's
# called. django.views.static.serve isn't the most efficient way to serve
# files at very high traffic, but for this app's scale on cPanel/Passenger
# it's the correct, safe default — USE_S3=True is the real fix if traffic
# ever outgrows it.
if not settings.USE_S3:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_static, {'document_root': settings.MEDIA_ROOT}),
    ]
