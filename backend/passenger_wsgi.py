"""
Entry point cPanel's Passenger looks for when a Python app's "Application
startup file" is left at its default. Point cPanel's Setup Python App at this
file (Application root = this backend/ directory, Application startup file =
passenger_wsgi.py, Application Entry point = application) — it just hands off
to the real Django WSGI app in core/wsgi.py.
"""

import sys
from pathlib import Path

# Passenger's working directory/sys.path handling varies by version — insert
# this directory explicitly so `import core` resolves regardless.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.wsgi import application  # noqa: E402
