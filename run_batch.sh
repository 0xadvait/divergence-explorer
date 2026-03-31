#!/usr/bin/env bash

set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-/etc/divergence-explorer/env}"

if [[ -r "$ENV_FILE" ]]; then
  log "Loading environment from $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
else
  log "Environment file not found at $ENV_FILE; continuing with current environment"
fi

REPO_DIR="${REPO_DIR:-$SCRIPT_DIR}"
WEB_ROOT="${WEB_ROOT:-/var/www/html}"
WEB_INDEX_PATH="${WEB_INDEX_PATH:-$WEB_ROOT/index.html}"
BATCH_SIZE="${BATCH_SIZE:-15}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOCK_FILE="${LOCK_FILE:-$REPO_DIR/.run_batch.lock}"
FINDINGS_PATH="${FINDINGS_PATH:-$REPO_DIR/results/findings.jsonl}"
REPORT_PATH="${REPORT_PATH:-$REPO_DIR/analysis/divergence_report.html}"
GIT_BRANCH="${GIT_BRANCH:-$(git -C "$REPO_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null || true)}"

if ! command -v flock >/dev/null 2>&1; then
  log "flock is required but was not found"
  exit 1
fi

mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"

if ! flock -n 9; then
  log "Another divergence batch is already running; exiting"
  exit 0
fi

cd "$REPO_DIR"

log "Running explorer batch with --batch-size $BATCH_SIZE"
"$PYTHON_BIN" -m src.explorer --batch-size "$BATCH_SIZE"

log "Regenerating dashboard"
"$PYTHON_BIN" analysis/generate_viz.py

log "Publishing dashboard to $WEB_INDEX_PATH"
mkdir -p "$(dirname "$WEB_INDEX_PATH")"
cp "$REPORT_PATH" "$WEB_INDEX_PATH"

FINDINGS_REL_PATH="${FINDINGS_PATH#$REPO_DIR/}"

log "Checking git state for $FINDINGS_REL_PATH"
git add -- "$FINDINGS_REL_PATH"

if git diff --cached --quiet -- "$FINDINGS_REL_PATH"; then
  log "No findings changes to commit"
  exit 0
fi

COMMIT_MESSAGE="${GIT_COMMIT_MESSAGE:-chore: update divergence findings $(date -u +'%Y-%m-%dT%H:%M:%SZ')}"

log "Committing updated findings"
git commit -m "$COMMIT_MESSAGE" -- "$FINDINGS_REL_PATH"

if [[ -z "$GIT_BRANCH" ]]; then
  log "Current branch could not be determined; skipping push"
  exit 0
fi

log "Pushing findings to $GIT_REMOTE/$GIT_BRANCH"
git push "$GIT_REMOTE" "$GIT_BRANCH"
