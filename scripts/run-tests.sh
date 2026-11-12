#!/bin/sh
# Runs both suites with no network and no API key. Used by `docker compose run --rm test`.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
[ -d "$ROOT/backend" ] || ROOT="$(dirname "$ROOT")"   # works from /work or from repo/scripts
unset OPENAI_API_KEY

echo "== backend (pytest) =="
cd "$ROOT/backend" && .venv/bin/python -m pytest -q

echo "== frontend (vitest) =="
cd "$ROOT/frontend" && npx --no-install vitest run
