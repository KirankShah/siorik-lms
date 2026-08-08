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

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from core.wsgi import application  # noqa: E402
