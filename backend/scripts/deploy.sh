#!/usr/bin/env bash
# Run after pulling new code into the cPanel Python app, with its virtualenv
# already active (cPanel's Setup Python App page shows the exact `source
# .../activate` command for this account — run that first).
#
# Usage: bash scripts/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."

pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Passenger restarts the app when this file's mtime changes — no separate
# "restart" button needed after this script runs.
mkdir -p tmp
touch tmp/restart.txt

echo "Deploy steps complete. Passenger will pick up the restart on the next request."
