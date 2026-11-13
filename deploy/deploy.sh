#!/usr/bin/env bash
# Deploys a version of the app to THIS server, checks it from outside, and puts
# the previous version back by itself if the new one does not come up healthy.
#
#   bash deploy/deploy.sh                 deploy origin/main
#   bash deploy/deploy.sh v1.4.0          deploy a tag or a commit
#   bash deploy/deploy.sh --dry-run [REF] show what would change, change nothing
#   bash deploy/deploy.sh --rollback      go back to the version that was running before the last deploy
#
# Run it as the deploy user, from the repository on the server. Full procedure:
# docs/deployment/06-deploy-and-rollback.md.
#
# Settings (environment): COMPOSE_FILES (default: base + prod), SMOKE_URL
# (default https://$DOMAIN from .env), SMOKE_TIMEOUT seconds (default 900, the
# search models take minutes to load), SKIP_BACKUP=1 (staging only),
# ALLOW_UNMERGED=1 (staging only: deploy a commit that is not in main).
set -euo pipefail

# This script switches the repository to another version, which replaces this
# very file while it runs. Bash reads scripts as it goes, so run from a copy.
if [[ -z "${DEPLOY_SELF_COPY:-}" ]]; then
  repo="$(cd "$(dirname "$0")/.." && pwd)"
  copy="$(mktemp)"
  cp "$0" "$copy"
  DEPLOY_SELF_COPY=1 DEPLOY_REPO="$repo" exec bash "$copy" "$@"
fi
trap 'rm -f "$0"' EXIT
cd "$DEPLOY_REPO"

COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"
STATE=.deploy
SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-900}"
REQUIRED_SERVICES="postgres minio qdrant backend ingestion-worker mcp_server frontend caddy"

compose() {
  local args=()
  for f in $COMPOSE_FILES; do args+=(-f "$f"); done
  docker compose "${args[@]}" "$@"
}
say()  { printf '%s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
event() { mkdir -p "$STATE"; printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$STATE/history.log"; }

env_value() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- || true; }

smoke_url() {
  if [[ -n "${SMOKE_URL:-}" ]]; then printf '%s' "$SMOKE_URL"; return; fi
  local domain; domain="$(env_value DOMAIN)"
  [[ -n "$domain" ]] || die "DOMAIN is not set in .env (or give SMOKE_URL)"
  printf 'https://%s' "$domain"
}

services_up() {
  local running; running="$(compose ps --status running --services 2>/dev/null || true)"
  local s
  for s in $REQUIRED_SERVICES; do
    grep -qx "$s" <<<"$running" || { say "  not running: $s"; return 1; }
  done
}

worker_healthy() {
  compose exec -T ingestion-worker python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=5)" >/dev/null 2>&1
}

# Waits until every service runs and the outside checks pass.
wait_healthy() {
  local url deadline; url="$(smoke_url)"; deadline=$(( $(date +%s) + SMOKE_TIMEOUT ))
  say "Waiting for it to come up (up to $((SMOKE_TIMEOUT / 60)) minutes; the search models take a while to load)..."
  while (( $(date +%s) < deadline )); do
    if services_up >/dev/null 2>&1 && worker_healthy && bash deploy/smoke-test.sh "$url" >/tmp/ragconsumer-smoke.log 2>&1; then
      cat /tmp/ragconsumer-smoke.log
      return 0
    fi
    sleep 10
  done
  say "It did not become healthy in time. Last state:"
  services_up || true
  worker_healthy || say "  the ingestion worker does not answer"
  bash deploy/smoke-test.sh "$url" 2>&1 | tail -15 || true
  return 1
}

apply() {  # apply <sha>: switch the code and (re)start everything
  git checkout -q --detach "$1"
  compose build
  compose up -d --remove-orphans
}

resolve() {  # resolve <ref> -> full commit sha
  git rev-parse --verify --quiet "$1^{commit}" || die "'$1' is not a known tag, branch or commit (after fetching)"
}

# ---------------------------------------------------------------------------

MODE=deploy
DRY=0
REF=""
for arg in "$@"; do
  case "$arg" in
    --rollback) MODE=rollback ;;
    --dry-run)  DRY=1 ;;
    -h|--help)  sed -n '2,16p' "$DEPLOY_REPO/deploy/deploy.sh"; exit 0 ;;
    -*)         die "unknown option $arg" ;;
    *)          REF="$arg" ;;
  esac
done

[[ -f .env ]] || die "no .env here: this is not a configured server (see docs/deployment/04-secrets.md)"
git diff --quiet && git diff --cached --quiet || die "the repository has uncommitted changes to tracked files; the server must run exactly what is in git. Stash or discard them first."

CURRENT="$(git rev-parse HEAD)"

if [[ "$MODE" == "rollback" ]]; then
  [[ -f "$STATE/previous" ]] || die "no previous deploy is recorded, so there is nothing to go back to"
  TARGET="$(cat "$STATE/previous")"
  [[ "$TARGET" != "$CURRENT" ]] || die "the recorded previous version is the one already running; nothing to go back to"
  say "Rollback: $(git log -1 --format='%h %s' "$CURRENT") -> $(git log -1 --format='%h %s' "$TARGET")"
else
  git fetch -q --tags origin
  TARGET="$(resolve "${REF:-origin/main}")"
  if [[ "${ALLOW_UNMERGED:-}" != "1" ]] && ! git merge-base --is-ancestor "$TARGET" origin/main; then
    die "$TARGET is not in main. Only merged, reviewed work may be deployed (staging can override with ALLOW_UNMERGED=1)."
  fi
fi

if [[ "$TARGET" == "$CURRENT" && "$MODE" == "deploy" && "${FORCE:-}" != "1" ]]; then
  say "Already running $(git log -1 --format='%h %s' "$CURRENT"). Nothing to deploy (FORCE=1 redeploys anyway)."
  exit 0
fi

say "Running now : $(git log -1 --format='%h %s' "$CURRENT")"
say "Deploying   : $(git log -1 --format='%h %s' "$TARGET")"
if [[ "$MODE" == "deploy" ]]; then
  say "Changes:"; git log --format='  %h %s' "$CURRENT..$TARGET" 2>/dev/null | head -30
fi
MIGRATIONS="$(git diff --name-only "$CURRENT" "$TARGET" -- backend/alembic/versions 2>/dev/null || true)"
if [[ -n "$MIGRATIONS" && "$MODE" == "deploy" ]]; then
  say "DATABASE CHANGES in this version (applied automatically when the backend starts):"
  sed 's/^/  /' <<<"$MIGRATIONS"
  say "They are additive, so a rollback can put the old code back without undoing them; the backup taken first is the way back if one goes wrong."
elif [[ -n "$MIGRATIONS" ]]; then
  say "The version being left changed the database. Those changes stay in place; the older code runs on them because migrations are additive."
fi
[[ $DRY -eq 1 ]] && { say "Dry run: nothing changed."; exit 0; }

if [[ "$MODE" == "deploy" ]]; then
  if [[ "${SKIP_BACKUP:-}" == "1" ]]; then
    say "Skipping the pre-deploy backup (SKIP_BACKUP=1)."
  else
    say "Taking a backup before changing anything..."
    compose --profile tools run --rm -T backup backup || die "the backup failed, so nothing was deployed. Fix it first (or SKIP_BACKUP=1 on staging)."
  fi
fi

event "$MODE start ${CURRENT:0:9} -> ${TARGET:0:9}"
apply "$TARGET"

if wait_healthy; then
  event "$MODE ok ${TARGET:0:9}"
  docker image prune -f >/dev/null 2>&1 || true
  say "DEPLOY OK: now running $(git log -1 --format='%h %s' "$TARGET")"
  mkdir -p "$STATE"
  if [[ "$MODE" == "rollback" ]]; then
    rm -f "$STATE/previous"   # one step back only; deploy again to go forward
  else
    echo "$CURRENT" > "$STATE/previous"   # recorded only once the new version proved healthy
  fi
  exit 0
fi

event "$MODE FAILED ${TARGET:0:9}"
if [[ "$MODE" == "rollback" ]]; then
  die "the rollback itself did not come up healthy. See docs/deployment/06-deploy-and-rollback.md ('If a rollback fails')."
fi

say "The new version is not healthy. Putting $(git log -1 --format='%h' "$CURRENT") back..."
apply "$CURRENT"
if wait_healthy; then
  event "auto-rollback ok ${CURRENT:0:9}"
  say "ROLLED BACK: the previous version is running again. The new version was NOT deployed."
  if [[ -n "$MIGRATIONS" ]]; then say "The new version changed the database before it failed; the app works on the older code, but if anything looks wrong restore the pre-deploy backup."; fi
  exit 1
fi
event "auto-rollback FAILED ${CURRENT:0:9}"
die "the previous version did not come up either. See docs/deployment/06-deploy-and-rollback.md ('If a rollback fails')."
