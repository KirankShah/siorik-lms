#!/usr/bin/env bash
# Builds the frontend and deploys dist/ to the production document root:
# runs `npm run build` locally, then ships the result over the same SSH
# connection deploy.sh uses, replacing whatever's currently on the server.
#
# Uses tar-over-SSH rather than rsync: this dev machine has no rsync binary
# available (not even via WSL), and tar handles dotfiles (.htaccess) the
# same way scp's glob-based recursive copy doesn't reliably.
#
# Usage: ./deploy-frontend.sh
#
# Configure via environment variables, or edit the CHANGE_ME defaults below.
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/siorik_deploy}"
SSH_USER="${SSH_USER:-siorikco}"
SSH_HOST="${SSH_HOST:-enterprise.learnwithsiorik.com}"
SSH_PORT="${SSH_PORT:-22}"
# Document root the frontend vhost/subdomain serves. Everything in here
# EXCEPT .well-known/ (Let's Encrypt/SSL validation) and cgi-bin/ (cPanel-
# managed) gets replaced to match dist/ exactly — never delete those two.
REMOTE_FRONTEND_ROOT="${REMOTE_FRONTEND_ROOT:-/home/siorikco/enterprise.learnwithsiorik.com}"

for var_name in SSH_USER SSH_HOST REMOTE_FRONTEND_ROOT; do
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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
SSH_CMD=(ssh -i "$SSH_KEY" -p "$SSH_PORT" -o BatchMode=yes "$SSH_USER@$SSH_HOST")

echo "==> Building frontend (npm run build)"
(cd "$FRONTEND_DIR" && npm run build)

if [[ ! -f "$FRONTEND_DIR/dist/index.html" ]]; then
  echo "ERROR: $FRONTEND_DIR/dist/index.html not found after build — the build did not produce the expected output." >&2
  exit 1
fi

echo "==> Clearing old deployment at $REMOTE_FRONTEND_ROOT (preserving .well-known/ and cgi-bin/)"
"${SSH_CMD[@]}" "cd '$REMOTE_FRONTEND_ROOT' && find . -mindepth 1 -maxdepth 1 ! -name .well-known ! -name cgi-bin -exec rm -rf {} +"

echo "==> Uploading dist/ to $SSH_USER@$SSH_HOST:$REMOTE_FRONTEND_ROOT"
tar czf - -C "$FRONTEND_DIR/dist" . | "${SSH_CMD[@]}" "tar xzf - -C '$REMOTE_FRONTEND_ROOT'"

echo "==> Frontend deploy complete."
