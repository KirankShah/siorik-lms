#!/usr/bin/env bash
# Deploys the backend to production: SSHes into the cPanel server, confirms
# it's on (and pulls) main — not fresh-start — then runs the existing
# server-side deploy steps (backend/scripts/deploy.sh: pip install, migrate,
# collectstatic, Passenger restart-touch) inside the activated virtualenv.
#
# Usage: ./deploy.sh
#
# Configure via environment variables, or edit the CHANGE_ME defaults below.
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/siorik_deploy}"
SSH_USER="${SSH_USER:-siorikco}"
SSH_HOST="${SSH_HOST:-enterprise.learnwithsiorik.com}"
SSH_PORT="${SSH_PORT:-22}"
# Application Root on the server — where passenger_wsgi.py lives (repo root,
# not backend/ — see passenger_wsgi.py's own header comment).
REMOTE_APP_ROOT="${REMOTE_APP_ROOT:-/home/siorikco/api.enterprise.learnwithsiorik.com}"
# The exact `source .../activate` command cPanel's "Setup Python App" page
# shows for this account — copy it verbatim.
REMOTE_VENV_ACTIVATE="${REMOTE_VENV_ACTIVATE:-/home/siorikco/virtualenv/api.enterprise.learnwithsiorik.com/3.11/bin/activate}"

for var_name in SSH_USER SSH_HOST REMOTE_APP_ROOT REMOTE_VENV_ACTIVATE; do
  value="${!var_name}"
  if [[ "$value" == CHANGE_ME_* ]]; then
    echo "ERROR: $var_name is still a placeholder ($value)." >&2
    echo "Set it via environment variable, or edit the default at the top of this script." >&2
    exit 1
  fi
done

if [[ ! -f "$SSH_KEY" ]]; then
  echo "ERROR: SSH key not found at $SSH_KEY" >&2
  exit 1
fi

echo "==> Deploying backend to $SSH_USER@$SSH_HOST:$REMOTE_APP_ROOT"

# -o BatchMode=yes: fail immediately instead of hanging on a password prompt
# if key auth doesn't work, so a broken key surfaces as a loud error, not a
# silent hang.
ssh -i "$SSH_KEY" -p "$SSH_PORT" -o BatchMode=yes "$SSH_USER@$SSH_HOST" bash -s <<REMOTE_SCRIPT
set -euo pipefail

echo "==> cd into app root: $REMOTE_APP_ROOT"
cd "$REMOTE_APP_ROOT"

echo "==> activate virtualenv"
source "$REMOTE_VENV_ACTIVATE"

echo "==> confirm the server is on main, not fresh-start"
CURRENT_BRANCH="\$(git rev-parse --abbrev-ref HEAD)"
if [[ "\$CURRENT_BRANCH" != "main" ]]; then
  echo "ERROR: server is checked out on '\$CURRENT_BRANCH', not main. Refusing to deploy — check out main first." >&2
  exit 1
fi

echo "==> git pull origin main"
git pull origin main

echo "==> run backend/scripts/deploy.sh (pip install, migrate, collectstatic, Passenger restart)"
bash backend/scripts/deploy.sh
REMOTE_SCRIPT

echo "==> Backend deploy complete."
