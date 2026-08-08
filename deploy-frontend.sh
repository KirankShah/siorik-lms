#!/usr/bin/env bash
# Builds the frontend and deploys dist/ to the production document root:
# runs `npm run build` locally, then rsyncs the result over the same SSH
# connection deploy.sh uses, replacing whatever's currently on the server.
#
# Usage: ./deploy-frontend.sh
#
# Configure via environment variables, or edit the CHANGE_ME defaults below.
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/siorik_cpanel_key}"
SSH_USER="${SSH_USER:-CHANGE_ME_cpanel_username}"
SSH_HOST="${SSH_HOST:-CHANGE_ME_server_hostname_or_ip}"
SSH_PORT="${SSH_PORT:-22}"
# Document root the frontend vhost/subdomain serves. This gets REPLACED to
# match dist/ exactly (rsync --delete) — double check this points at the
# frontend's own directory, never anything shared with other content.
REMOTE_FRONTEND_ROOT="${REMOTE_FRONTEND_ROOT:-CHANGE_ME_/home/username/enterprise.learnwithsiorik.com}"

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

if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync is not installed/on PATH." >&2
  echo "Git Bash on Windows bundles ssh/scp but not rsync — install it (e.g. via MSYS2/Cygwin, or WSL) before running this script." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "==> Building frontend (npm run build)"
(cd "$FRONTEND_DIR" && npm run build)

if [[ ! -f "$FRONTEND_DIR/dist/index.html" ]]; then
  echo "ERROR: $FRONTEND_DIR/dist/index.html not found after build — the build did not produce the expected output." >&2
  exit 1
fi

echo "==> Uploading dist/ to $SSH_USER@$SSH_HOST:$REMOTE_FRONTEND_ROOT (replacing existing contents)"
# --delete removes files on the server that no longer exist locally (e.g. a
# previous build's hashed JS/CSS filenames), so the document root always
# matches this exact build rather than accumulating every build ever run.
rsync -avz --delete \
  -e "ssh -i $SSH_KEY -p $SSH_PORT -o BatchMode=yes" \
  "$FRONTEND_DIR/dist/" \
  "$SSH_USER@$SSH_HOST:$REMOTE_FRONTEND_ROOT/"

echo "==> Frontend deploy complete."
