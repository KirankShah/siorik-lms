"""
Entry point cPanel's Passenger looks for at the Application Root. This repo's
Django project lives one level down in backend/ (not at the repo root), so
this just adds that directory to sys.path and hands off to the real WSGI app
in backend/core/wsgi.py.

cPanel's Setup Python App: Application root = repo root, Application startup
file = passenger_wsgi.py, Application Entry point = application.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Resource PDFs live outside the deployed checkout on cPanel. This value is
# also exported by backend/scripts/deploy.sh so migrations and deploy checks
# use the same path as Passenger.
os.environ.setdefault('RESOURCE_MEDIA_ROOT', os.path.join(os.path.expanduser('~'), 'siorik_lms_media'))
os.makedirs(os.environ['RESOURCE_MEDIA_ROOT'], exist_ok=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from core.wsgi import application  # noqa: E402
