#!/usr/bin/env bash
# Run after pulling new code into the cPanel Python app, with its virtualenv
# already active (cPanel's Setup Python App page shows the exact `source
# .../activate` command for this account — run that first).
#
# Usage: bash backend/scripts/deploy.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/.."
REPO_ROOT="$BACKEND_DIR/.."

cd "$BACKEND_DIR"
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Passenger restarts the app when this file's mtime changes — no separate
# "restart" button needed after this script runs. Application Root is the
# repo root (passenger_wsgi.py lives there, not in backend/), so that's
# where Passenger watches for tmp/restart.txt.
mkdir -p "$REPO_ROOT/tmp"
touch "$REPO_ROOT/tmp/restart.txt"

echo "Deploy steps complete. Passenger will pick up the restart on the next request."
