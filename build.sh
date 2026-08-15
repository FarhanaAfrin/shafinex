#!/usr/bin/env bash
# Build both halves into one deployable service.
# Render runs this as the build command; it also works locally.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing Python dependencies"
pip install --upgrade pip
pip install -r "$ROOT/backend/requirements.txt"

# Render's native runtimes all ship node + npm, so this runs there as well as locally.
if command -v npm >/dev/null 2>&1; then
  echo "==> Building the frontend"
  cd "$ROOT/frontend"
  npm ci --no-audit --no-fund
  npm run build
elif [ -f "$ROOT/frontend/dist/index.html" ]; then
  echo "!! npm not found — using the committed frontend/dist"
else
  echo "!! npm not found and no frontend/dist to fall back on." >&2
  echo "   The service would start API-only, with no UI. Failing the build instead." >&2
  exit 1
fi

echo "==> Build finished"
