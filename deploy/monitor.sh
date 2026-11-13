#!/usr/bin/env bash
# Watches this server and tells people when something is wrong, and again when
# it is fixed. Run every few minutes by a systemd timer
# (deploy/install-monitor-timer.sh). Safe to run by hand: it prints what it found.
#
#   bash deploy/monitor.sh            check, alert on a change
#   bash deploy/monitor.sh --test     send a test alert to every configured channel
#
# What it checks: every service is running and has not been restarting or killed
# for lack of memory; the ingestion worker answers; the site works from outside
# (the same smoke test as a deploy); the disk is not filling up; last night's
# backup happened; the HTTPS certificate is not about to expire; no document is
# stuck waiting to be indexed or failing for reasons that are the system's fault.
#
# Where alerts go (set in .env or the environment; at least one is needed):
#   ALERT_WEBHOOK_URL   Slack / Mattermost / Teams / Discord incoming webhook
#   ALERT_NTFY_URL      an ntfy topic, e.g. https://ntfy.sh/your-secret-topic
#   HEARTBEAT_URL       pinged after every fully healthy run (healthchecks.io style),
#                       so an outside service notices if this whole server goes silent
# Other settings: MONITOR_DISK_MAX (default 85, percent), MONITOR_BACKUP_MAX_HOURS
# (default 26), MONITOR_CERT_MIN_DAYS (default 14), MONITOR_DOC_WAIT_MINUTES
# (default 90), MONITOR_REMIND_HOURS (default 6),
# MONITOR_STATE_DIR, COMPOSE_FILES, SMOKE_URL.
set -uo pipefail
cd "$(dirname "$0")/.."

COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"
STATE_DIR="${MONITOR_STATE_DIR:-/var/lib/ragconsumer-monitor}"
REQUIRED_SERVICES="postgres minio qdrant backend ingestion-worker mcp_server frontend caddy"

env_value() {
  local current="${!1:-}"
  if [[ -n "$current" ]]; then printf '%s' "$current"; return; fi
  grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- || true
}
ALERT_WEBHOOK_URL="$(env_value ALERT_WEBHOOK_URL)"
ALERT_NTFY_URL="$(env_value ALERT_NTFY_URL)"
HEARTBEAT_URL="$(env_value HEARTBEAT_URL)"
DOMAIN="$(env_value DOMAIN)"
DISK_MAX="${MONITOR_DISK_MAX:-85}"
BACKUP_MAX_HOURS="${MONITOR_BACKUP_MAX_HOURS:-26}"
CERT_MIN_DAYS="${MONITOR_CERT_MIN_DAYS:-14}"
REMIND_HOURS="${MONITOR_REMIND_HOURS:-6}"
HOST_LABEL="${MONITOR_NAME:-$(hostname)}"

compose() {
  local args=() f
  for f in $COMPOSE_FILES; do args+=(-f "$f"); done
  docker compose "${args[@]}" "$@"
}

send_alert() {  # send_alert <title> <body>
  local title="$1" body="$2" text sent=0
  text="[$HOST_LABEL] $title"$'\n'"$body"
  if [[ -n "$ALERT_WEBHOOK_URL" ]]; then
    # "text" is read by Slack, Mattermost and Teams; "content" by Discord.
    local payload; payload="$(python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1], "content": sys.argv[1]}))' "$text" 2>/dev/null || python -c 'import json,sys; print(json.dumps({"text": sys.argv[1], "content": sys.argv[1]}))' "$text")"
    curl -fsS --max-time 15 -H 'content-type: application/json' -d "$payload" "$ALERT_WEBHOOK_URL" >/dev/null && sent=1 || echo "WARNING: could not reach ALERT_WEBHOOK_URL" >&2
  fi
  if [[ -n "$ALERT_NTFY_URL" ]]; then
    curl -fsS --max-time 15 -H "Title: [$HOST_LABEL] $title" -d "$body" "$ALERT_NTFY_URL" >/dev/null && sent=1 || echo "WARNING: could not reach ALERT_NTFY_URL" >&2
  fi
  [[ $sent -eq 1 ]] || echo "WARNING: no alert channel worked or is configured (ALERT_WEBHOOK_URL / ALERT_NTFY_URL); nobody was told." >&2
}

if [[ "${1:-}" == "--test" ]]; then
  send_alert "Test alert" "If you can read this, alerts from this server reach you."
  echo "Test alert sent to the configured channels."
  exit 0
fi

problems=()
problem() { problems+=("$1"); }

# 1. services up, not restart-looping, not killed for memory
running="$(compose ps --status running --services 2>/dev/null || true)"
for s in $REQUIRED_SERVICES; do
  grep -qx "$s" <<<"$running" || problem "service $s is not running"
done
for id in $(compose ps -q 2>/dev/null); do
  info="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}} {{.State.OOMKilled}} {{.RestartCount}}' "$id" 2>/dev/null || true)"
  set -- $info
  [[ "${2:-false}" == "true" ]] && problem "service ${1:-?} was killed for lack of memory"
  [[ "${3:-0}" -ge 3 ]] && problem "service ${1:-?} keeps restarting (${3} times)"
done

# 2. the ingestion worker answers
compose exec -T ingestion-worker python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=5)" >/dev/null 2>&1 \
  || problem "the document worker does not answer (uploaded documents will not be indexed)"

# 3. the site, from outside the containers (DNS, certificate, proxy, app)
url="${SMOKE_URL:-}"; [[ -z "$url" && -n "$DOMAIN" ]] && url="https://$DOMAIN"
if [[ -n "$url" ]]; then
  smoke="$(bash deploy/smoke-test.sh "$url" 2>&1)" || problem "the site fails its outside check: $(grep FAIL <<<"$smoke" | head -3 | sed 's/^ *FAIL  //' | paste -sd ';' -)"
else
  problem "DOMAIN is not set, so the site cannot be checked"
fi

# 4. disk
used="$(df --output=pcent / 2>/dev/null | tail -1 | tr -dc '0-9')"
[[ -n "$used" && "$used" -ge "$DISK_MAX" ]] && problem "the disk is ${used}% full (limit ${DISK_MAX}%)"

# 5. last night's backup
project="${COMPOSE_PROJECT_NAME:-$(basename "$PWD" | tr 'A-Z' 'a-z')}"
volume="${project}_backup_data"
if [[ "${MONITOR_BACKUP:-on}" != "off" ]]; then
  stamp=""
  [[ -n "$volume" ]] && stamp="$(docker run --rm -v "$volume":/b:ro --entrypoint head ragconsumer-backup -n1 /b/last-success 2>/dev/null || true)"
  if [[ -z "$stamp" ]]; then
    problem "no successful backup has been recorded"
  else
    when="$(date -d "$stamp" +%s 2>/dev/null || echo 0)"
    age_h=$(( ( $(date +%s) - when ) / 3600 ))
    (( age_h > BACKUP_MAX_HOURS )) && problem "the last successful backup was ${age_h} hours ago (limit ${BACKUP_MAX_HOURS})"
  fi
fi

# 6. certificate (a real domain only; Caddy renews on its own, so this means renewal is broken)
if [[ -n "$DOMAIN" && "$DOMAIN" != localhost* && "$DOMAIN" != *.localhost ]]; then
  end="$(echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
  if [[ -z "$end" ]]; then
    problem "the HTTPS certificate could not be read"
  else
    days=$(( ( $(date -d "$end" +%s) - $(date +%s) ) / 86400 ))
    (( days < CERT_MIN_DAYS )) && problem "the HTTPS certificate expires in ${days} days (renewal is not working)"
  fi
fi

# 7. documents that are not getting indexed (a worker that is up but stuck, a backlog,
#    or failures that are the system's fault rather than the file's)
doc_wait="${MONITOR_DOC_WAIT_MINUTES:-90}"
doc_sql="select (select count(*) from documents where status in ('uploaded','processing') and updated_at < now() - interval '${doc_wait} minutes') || ' ' || (select count(*) from documents where status = 'failed' and error_message in ('unexpected','timed_out','index_outdated') and updated_at > now() - interval '24 hours')"
if counts="$(compose exec -T postgres sh -c 'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$0"' "$doc_sql" 2>/dev/null)" && [[ -n "$counts" ]]; then
  set -- $counts
  (( ${1:-0} > 0 )) && problem "${1} document(s) have been waiting or processing for over ${doc_wait} minutes without progress"
  (( ${2:-0} > 0 )) && problem "${2} document(s) failed because of the system (not the file) in the last 24 hours: check the worker logs, and re-index if the index is outdated"
else
  problem "the database could not be queried for stuck documents"
fi

# --- tell people only when something changes (or as a reminder) ---------------
mkdir -p "$STATE_DIR" 2>/dev/null || { STATE_DIR="$(mktemp -d)"; echo "WARNING: cannot write the state folder; using a temporary one" >&2; }
current="$(printf '%s\n' "${problems[@]+"${problems[@]}"}" | sed '/^$/d' | sort)"
previous="$(cat "$STATE_DIR/problems" 2>/dev/null || true)"
now="$(date +%s)"
last_alert="$(cat "$STATE_DIR/last-alert" 2>/dev/null || echo 0)"

if [[ -z "$current" ]]; then
  echo "OK: all checks passed"
  if [[ -n "$previous" ]]; then
    send_alert "RECOVERED" "Everything is working again. It had been reporting:"$'\n'"$previous"
  fi
  : > "$STATE_DIR/problems"
  [[ -n "$HEARTBEAT_URL" ]] && curl -fsS --max-time 15 "$HEARTBEAT_URL" >/dev/null 2>&1
  exit 0
fi

echo "PROBLEMS:"; sed 's/^/  - /' <<<"$current"
if [[ "$current" != "$previous" ]]; then
  send_alert "PROBLEM" "$current"
  echo "$now" > "$STATE_DIR/last-alert"
elif (( now - last_alert >= REMIND_HOURS * 3600 )); then
  send_alert "STILL BROKEN" "$current"
  echo "$now" > "$STATE_DIR/last-alert"
fi
printf '%s\n' "$current" > "$STATE_DIR/problems"
exit 1
