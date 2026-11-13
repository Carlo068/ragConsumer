#!/usr/bin/env bash
# Rehearses deploy and rollback on a scratch copy of the whole stack
# (compose project "ragdeploytest", local test certificate, nothing shared
# with the running dev stack), using the current files of this repository.
#
#   bash deploy/test-deploy.sh        (takes 10-20 minutes the first time: images build and ~1 GB of models download)
#
# Scenarios: first deploy; a good release with a database migration; a broken
# release that must roll back by itself; a manual rollback across that
# migration; the refusals (dirty tree, unmerged commit, backup failure,
# nothing to do); then the monitor (alerts on a change, once, with recovery),
# and that the access log never records an invitation token.
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
  [[ -n "${RECV_PID:-}" ]] && kill "$RECV_PID" >/dev/null 2>&1
  ( cd "$T/work" 2>/dev/null && docker compose $FILES --profile tools down -v --remove-orphans >/dev/null 2>&1 )
  rm -rf "$T"
}
trap cleanup EXIT

dc() { ( cd "$T/work" && docker compose $FILES "$@" ); }
deploy() { ( cd "$T/work" && bash deploy/deploy.sh "$@" ) ; }
head_of() { git -C "$T/work" rev-parse --short HEAD; }
in_backend() { dc exec -T backend sh -c "$1"; }
# The migration bookkeeping is the owner's: the services' own roles cannot read it.
in_migrate() { dc run --rm --no-deps -T --entrypoint sh migrate -c "$1"; }
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

HEAD_REV="$(in_migrate 'alembic heads' | awk '{print $1}' | head -1)"
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
[[ "$(in_migrate 'alembic current 2>/dev/null' | grep -c ffff00000001)" == "1" ]] && ok "the migration was applied" || bad "migration not applied"

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
grep -q "database is newer than this version" <(dc logs migrate 2>&1) && ok "v1 started on the newer database (migrations are additive)" || bad "v1 did not report starting on the newer database"
[[ "$(wc -l < "$T/work/.deploy/history.log")" -ge 6 ]] && ok "every step is in the deploy history" || bad "history is incomplete"

echo "Monitoring (v1 is running; alerts go to a local receiver)"
cat > "$T/recv.py" <<'EOF'
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
LOG = sys.argv[2]
class H(BaseHTTPRequestHandler):
    def _log(self, body=""):
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{self.command} {self.path} {body}\n")
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def do_GET(self): self._log()
    def do_POST(self): self._log(self.rfile.read(int(self.headers.get("content-length", 0))).decode())
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
EOF
: > "$T/alerts.log"
python "$T/recv.py" 18099 "$T/alerts.log" & RECV_PID=$!
sleep 1
monitor() { ( cd "$T/work" && MONITOR_STATE_DIR="$T/mon" ALERT_WEBHOOK_URL=http://127.0.0.1:18099/hook HEARTBEAT_URL=http://127.0.0.1:18099/beat bash deploy/monitor.sh "$@" ); }
alerts() { grep -c 'POST /hook' "$T/alerts.log" || true; }
beats()  { grep -c 'GET /beat' "$T/alerts.log" || true; }

KEY="$(docker run --rm --entrypoint sh ragconsumer-backup -c 'age-keygen 2>&1 | grep -o "age1[a-z0-9]*" | head -1')"
dc --profile tools run --rm -T -e BACKUP_ALLOW_LOCAL_ONLY=true -e BACKUP_AGE_RECIPIENT="$KEY" backup backup >/dev/null 2>&1 && ok "a backup exists, so last night's backup check can pass" || bad "could not make a backup"

out="$(monitor 2>&1)"; code=$?
[[ $code -eq 0 ]] && grep -q "OK: all checks passed" <<<"$out" && ok "a healthy server: all checks pass" || { bad "healthy server reported problems: $out"; }
[[ "$(alerts)" == "0" && "$(beats)" == "1" ]] && ok "no alert, and the outside heartbeat was pinged" || bad "alerts=$(alerts) heartbeats=$(beats)"

dc stop ingestion-worker >/dev/null 2>&1
out="$(monitor 2>&1)"; code=$?
[[ $code -ne 0 ]] && grep -q "ingestion-worker" <<<"$out" && ok "a stopped worker is detected" || bad "stopped worker not detected: $out"
[[ "$(alerts)" == "1" ]] && grep -q "ingestion-worker" "$T/alerts.log" && ok "and one alert names it" || bad "alerts=$(alerts)"
monitor >/dev/null 2>&1
[[ "$(alerts)" == "1" ]] && ok "the same problem is not announced again on the next run" || bad "duplicate alert (alerts=$(alerts))"
[[ "$(beats)" == "1" ]] && ok "and no heartbeat is sent while unhealthy" || bad "heartbeat sent while unhealthy"
dc start ingestion-worker >/dev/null 2>&1
for _ in $(seq 1 40); do dc exec -T ingestion-worker python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=3)" >/dev/null 2>&1 && break; sleep 3; done
out="$(monitor 2>&1)"; code=$?
[[ $code -eq 0 ]] && ok "fixed: the next check passes" || bad "still failing after the fix: $out"
grep -q "RECOVERED" "$T/alerts.log" && [[ "$(alerts)" == "2" ]] && ok "and a recovery message is sent" || bad "no recovery message (alerts=$(alerts))"

out="$(MONITOR_DISK_MAX=1 monitor 2>&1)"; code=$?
[[ $code -ne 0 ]] && grep -q "disk is" <<<"$out" && ok "a full disk is detected (limit lowered to force it)" || bad "disk check did not trigger: $out"
monitor >/dev/null 2>&1

VOLNAME=ragdeploytest_backup_data
docker run --rm -v $VOLNAME:/b --entrypoint sh ragconsumer-backup -c 'echo 2020-01-01T00:00:00+00:00 > /b/last-success'
out="$(monitor 2>&1)"; code=$?
[[ $code -ne 0 ]] && grep -q "last successful backup" <<<"$out" && ok "a stale backup is detected" || bad "stale backup not detected: $out"
docker run --rm -v $VOLNAME:/b --entrypoint sh ragconsumer-backup -c 'rm -f /b/last-success'
out="$(monitor 2>&1)"; grep -q "no successful backup" <<<"$out" && ok "a missing backup record is detected" || bad "missing backup not detected: $out"
dc --profile tools run --rm -T -e BACKUP_ALLOW_LOCAL_ONLY=true -e BACKUP_AGE_RECIPIENT="$KEY" backup backup >/dev/null 2>&1
monitor >/dev/null 2>&1 && ok "a new backup clears it" || bad "still failing after a new backup"

dc stop ingestion-worker >/dev/null 2>&1   # so it cannot pick the test document up itself
dc exec -T backend python - <<'EOF' >/dev/null 2>&1
import datetime as dt
from app.db import SessionLocal
from app.models import Collection, Document, DocumentStatus, User
with SessionLocal() as db:
    user = User(email="monitor-test@example.test", password_hash="x")
    matter = Collection(name="monitor test")
    db.add_all([user, matter]); db.flush()
    old = dt.datetime.now() - dt.timedelta(hours=5)
    db.add(Document(collection_id=matter.id, uploaded_by=user.id, source_filename="stuck.pdf", object_key="k/stuck.pdf", status=DocumentStatus.uploaded, updated_at=old))
    db.commit()
EOF
out="$(monitor 2>&1)"; code=$?
[[ $code -ne 0 ]] && grep -q "waiting or processing" <<<"$out" && ok "a document stuck waiting to be indexed is detected" || bad "stuck document not detected: $out"
sql_w() { dc exec -T postgres sh -c 'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$0"' "$1" >/dev/null 2>&1; }
sql_w "update documents set status='failed', error_message='unexpected', updated_at=now() where source_filename='stuck.pdf'"
out="$(monitor 2>&1)"; grep -q "failed because of the system" <<<"$out" && ok "a failure caused by the system (not the file) is detected" || bad "system failure not detected: $out"
sql_w "update documents set error_message='no_text' where source_filename='stuck.pdf'"
dc start ingestion-worker >/dev/null 2>&1
for _ in $(seq 1 40); do dc exec -T ingestion-worker python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=3)" >/dev/null 2>&1 && break; sleep 3; done
monitor >/dev/null 2>&1 && ok "a file that simply has no text does not raise an alert" || bad "alerted on a file-caused failure"
out="$(monitor --test 2>&1)"; grep -q "Test alert" "$T/alerts.log" && ok "the test alert reaches the channel" || bad "test alert not delivered: $out"
out="$(cd "$T/work" && MONITOR_STATE_DIR="$T/mon2" bash deploy/monitor.sh --test 2>&1)"
grep -q "no alert channel" <<<"$out" && ok "with no channel configured it says nobody was told" || bad "silent when no channel is configured: $out"

echo "Access log never records an invitation token"
curl -sk -o /dev/null -H 'Referer: https://localhost/invite/SECRETTOKEN4242' https://localhost/api/invites/SECRETTOKEN4242
curl -sk -o /dev/null -X POST https://localhost/api/invites/SECRETTOKEN4242/accept -H 'content-type: application/json' -d '{}'
sleep 2
log="$(dc exec -T caddy sh -c 'cat /var/log/caddy/access.log' 2>/dev/null)"
[[ -n "$log" ]] && ok "requests are written to the access log file" || bad "no access log"
! grep -q SECRETTOKEN4242 <<<"$log" && grep -q "invite/REDACTED" <<<"$log" && ok "the invitation token is scrubbed from addresses and from Referer" || bad "an invitation token appears in the access log"

echo
if [[ $fail -eq 0 ]]; then echo "DEPLOY REHEARSAL PASSED"; else echo "DEPLOY REHEARSAL FAILED"; fi
exit $fail
