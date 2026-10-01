#!/usr/bin/env bash
# Refresh the catalogue: re-export the listings, then tell the running backend
# to pick the new file up. Run it by hand, or from a system cron once the
# agency has settled on how often the data should change.
#
#   ./run_and_reload.sh              # scrape + reload
#   SKIP_RELOAD=1 ./run_and_reload.sh   # scrape only
#
# ADMIN_TOKEN is read from backend/.env unless already set in the environment.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(dirname "$script_dir")"

OUTPUT="${OUTPUT:-$repo_root/annunci.json}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
PYTHON="${PYTHON:-python3}"

log() { printf '==> %s\n' "$1"; }
die() { printf 'error: %s\n' "$1" >&2; exit 1; }

# --- scrape ------------------------------------------------------------------

log "Exporting listings to $OUTPUT"
# The scraper writes atomically, so a failure here leaves the previous export
# in place and the backend keeps serving it.
"$PYTHON" "$script_dir/scrape_listings.py" --output "$OUTPUT"

# --- reload ------------------------------------------------------------------

if [[ -n "${SKIP_RELOAD:-}" ]]; then
  log "SKIP_RELOAD set; leaving the backend to pick it up on its next restart"
  exit 0
fi

if [[ -z "${ADMIN_TOKEN:-}" && -f "$repo_root/backend/.env" ]]; then
  # Read it without sourcing the file, so nothing else in .env is executed.
  ADMIN_TOKEN="$(grep -E '^ADMIN_TOKEN=' "$repo_root/backend/.env" | tail -1 | cut -d= -f2- | tr -d '"'"'"'' || true)"
fi

[[ -n "${ADMIN_TOKEN:-}" ]] || die "ADMIN_TOKEN not set and not found in backend/.env"

log "Reloading $BACKEND_URL"
status="$(
  curl -sS -o /tmp/reload-response.$$ -w '%{http_code}' \
    -X POST "$BACKEND_URL/api/admin/reload" \
    -H "Authorization: Bearer $ADMIN_TOKEN"
)" || die "could not reach $BACKEND_URL — is the backend running?"

body="$(cat "/tmp/reload-response.$$")"
rm -f "/tmp/reload-response.$$"

[[ "$status" == "200" ]] || die "reload failed (HTTP $status): $body"

log "Reloaded: $body"
