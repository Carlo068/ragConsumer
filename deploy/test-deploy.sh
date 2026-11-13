#!/usr/bin/env bash
# Rehearses deploy and rollback on a scratch copy of the whole stack
# (compose project "ragdeploytest", local test certificate, nothing shared
# with the running dev stack), using the current files of this repository.
#
#   bash deploy/test-deploy.sh        (takes 10-20 minutes the first time: images build and ~1 GB of models download)
#
# Scenarios: first deploy; a good release with a database migration; a broken
# release that must roll back by itself; a manual rollback across that
# migration; and the refusals (dirty tree, unmerged commit, backup failure,
# nothing to do).
set -uo pipefail
cd "$(dirname "$0")/.."
SRC="$PWD"
export MSYS_NO_PATHCONV=1
export COMPOSE_PROJECT_NAME=ragdeploytest
export SMOKE_INSECURE=1
FILES="-f docker-compose.yml -f docker-compose.prod.yml"
fail=0
ok()  { printf '  PASS  %s\n' "$1"; }
bad() { printf '  FAIL  %s\n' "$1"; fail=1; }
T="$(mktemp -d)"; command -v cygpath >/dev/null && T="$(cygpath -m "$T")"

cleanup() {
  cd "$SRC"
  ( cd "$T/work" 2>/dev/null && docker compose $FILES --profile tools down -v --remove-orphans >/dev/null 2>&1 )
  rm -rf "$T"
}
trap cleanup EXIT

dc() { ( cd "$T/work" && docker compose $FILES "$@" ); }
deploy() { ( cd "$T/work" && bash deploy/deploy.sh "$@" ) ; }
head_of() { git -C "$T/work" rev-parse --short HEAD; }
in_backend() { dc exec -T backend sh -c "$1"; }
git_w() { git -C "$T/work" "$@"; }
git_s() { git -C "$T/seed" "$@"; }

echo "Setup: a scratch origin and server copy of the current files"
mkdir -p "$T/seed"
git ls-files -co --exclude-standard -z | tar --null -T - -cf - | tar -xf - -C "$T/seed"
git_s init -q -b main && git_s config user.email t@example.test && git_s config user.name test
git_s add -A >/dev/null 2>&1 && git_s commit -q -m "v1" && ok "release v1 committed"
git clone -q --bare "$T/seed" "$T/origin.git"
git clone -q "$T/origin.git" "$T/work"
git_w config user.email t@example.test; git_w config user.name test
cp .env "$T/work/.env"; printf '\nDOMAIN=localhost\n' >> "$T/work/.env"
V1="$(head_of)"

echo "First deploy"
FORCE=1 SKIP_BACKUP=1 deploy >"$T/d1.log" 2>&1 && ok "v1 deploys and passes the smoke test" || { bad "first deploy failed"; tail -30 "$T/d1.log"; exit 1; }
[[ "$(head_of)" == "$V1" ]] && ok "the server is on v1" || bad "wrong version"
FORCE=1 SKIP_BACKUP=1 deploy --dry-run >/dev/null 2>&1 && ok "dry run works" || bad "dry run failed"
out="$(deploy 2>&1)"; grep -q "Already running" <<<"$out" && ok "deploying what is already running does nothing" || bad "not idempotent: $out"

HEAD_REV="$(in_backend 'alembic heads' | awk '{print $1}' | head -1)"
echo "Release v2: a code change and a database migration"
printf '\n# v2-marker\n' >> "$T/seed/backend/app/main.py"
cat > "$T/seed/backend/alembic/versions/ffff00000001_noop.py" <<EOF
"""no-op migration used by the deploy rehearsal"""
revision = "ffff00000001"
down_revision = "$HEAD_REV"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
EOF
git_s add -A >/dev/null && git_s commit -q -m "v2: marker and a migration" && git_s push -q "$T/origin.git" main
out="$(deploy --dry-run 2>&1)"; grep -q "DATABASE CHANGES" <<<"$out" && ok "the plan announces the database change" || bad "migration not announced"
[[ "$(head_of)" == "$V1" ]] && ok "and the dry run changed nothing" || bad "dry run moved the code"

echo "Refusals"
SKIP_BACKUP= deploy >"$T/d.log" 2>&1; code=$?
[[ $code -ne 0 ]] && grep -q "nothing was deployed" "$T/d.log" && [[ "$(head_of)" == "$V1" ]] && ok "a failing backup stops the deploy and changes nothing" || bad "backup failure did not stop the deploy"
echo "# stray edit" >> "$T/work/docker-compose.yml"
SKIP_BACKUP=1 deploy >"$T/d.log" 2>&1; code=$?
[[ $code -ne 0 ]] && grep -q "uncommitted changes" "$T/d.log" && ok "a modified working tree is refused" || bad "dirty tree not refused"
git_w checkout -q -- docker-compose.yml
git_w checkout -q -b local-only && echo x > "$T/work/local.txt" && git_w add local.txt && git_w commit -q -m "never merged" && git_w checkout -q --detach "$V1"
SKIP_BACKUP=1 deploy local-only >"$T/d.log" 2>&1; code=$?
[[ $code -ne 0 ]] && grep -q "is not in main" "$T/d.log" && ok "a commit that is not in main is refused" || bad "unmerged commit not refused"

echo "Deploying v2"
SKIP_BACKUP=1 deploy >"$T/d2.log" 2>&1 && ok "v2 deploys and passes the smoke test" || { bad "v2 deploy failed"; tail -30 "$T/d2.log"; }
V2="$(head_of)"
[[ "$(cat "$T/work/.deploy/previous")" == "$(git_w rev-parse "$V1")" ]] && ok "the previous version is recorded" || bad "previous version not recorded"
[[ "$(in_backend 'grep -c v2-marker app/main.py')" == "1" ]] && ok "the running container really contains v2's code" || bad "container does not run v2"
[[ "$(in_backend 'alembic current' | grep -c ffff00000001)" == "1" ]] && ok "the migration was applied" || bad "migration not applied"

echo "Release v3: broken (the backend cannot start)"
printf '\nthis is not python (\n' >> "$T/seed/backend/app/main.py"
git_s commit -q -am "v3: broken" && git_s push -q "$T/origin.git" main
SMOKE_TIMEOUT=150 SKIP_BACKUP=1 deploy >"$T/d3.log" 2>&1; code=$?
[[ $code -ne 0 ]] && ok "the deploy reports failure" || bad "a broken release was reported as success"
grep -q "ROLLED BACK" "$T/d3.log" && ok "and rolls back by itself" || { bad "no automatic rollback"; tail -20 "$T/d3.log"; }
[[ "$(head_of)" == "$V2" ]] && ok "the server is back on v2" || bad "server is on $(head_of), expected $V2"
bash "$T/work/deploy/smoke-test.sh" https://localhost >/dev/null 2>&1 && ok "and answers correctly" || bad "not healthy after the automatic rollback"

echo "Manual rollback across the migration (v2 -> v1)"
SKIP_BACKUP=1 deploy --rollback >"$T/d4.log" 2>&1 && ok "rollback to v1 completes and passes the smoke test" || { bad "rollback failed"; tail -30 "$T/d4.log"; }
[[ "$(head_of)" == "$V1" ]] && ok "the server is on v1" || bad "not on v1"
[[ "$(in_backend 'grep -c v2-marker app/main.py' || true)" == "0" ]] && ok "the container runs v1's code" || bad "container still has v2's code"
grep -q "database is newer than this version" <(dc logs backend 2>&1) && ok "v1 started on the newer database (migrations are additive)" || bad "v1 did not report starting on the newer database"
[[ "$(wc -l < "$T/work/.deploy/history.log")" -ge 6 ]] && ok "every step is in the deploy history" || bad "history is incomplete"

echo
if [[ $fail -eq 0 ]]; then echo "DEPLOY REHEARSAL PASSED"; else echo "DEPLOY REHEARSAL FAILED"; fi
exit $fail
