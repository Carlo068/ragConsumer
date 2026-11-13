#!/usr/bin/env bash
# Restore drill: proves a backup of the RUNNING stack can really be restored.
#
#   bash deploy/test-backup.sh
#
# It backs up the running stack, restores that backup into a second, empty set
# of data stores (compose project "ragrestore", own volumes, no published
# ports), and compares the two independently of the backup tool's own checks:
# row counts of every table, the checksum of every stored document, and the
# vectors in the search index. It also tries the ways a restore can go wrong
# (wrong key, damaged file, no confirmation) and the off-server path, using
# the scratch MinIO as the off-server bucket. The live stack is only read.
set -uo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

LIVE=(docker compose)
REST=(docker compose -p ragrestore -f docker-compose.yml -f deploy/test/restore-override.yml)
VOL=ragbackup_test
fail=0
ok()  { printf '  PASS  %s\n' "$1"; }
bad() { printf '  FAIL  %s\n' "$1"; fail=1; }
check() { local what="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$what"; else bad "$what"; fi; }
refuse() { local what="$1" want="$2"; shift 2; local out; out="$("$@" 2>&1)"; local code=$?
  if [[ $code -ne 0 ]] && grep -qF -- "$want" <<<"$out"; then ok "$what"; else bad "$what (exit $code: $(tail -c 200 <<<"$out"))"; fi; }

# $1 = compose array name ("LIVE" or "REST"); the rest = backup-tool arguments
tool()  { local -n c=$1; shift; "${c[@]}" --profile tools run --rm -T -v $VOL:/backups backup "$@"; }
psqlx() { local -n c=$1; shift; "${c[@]}" exec -T postgres sh -c 'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$0"' "$1"; }

cleanup() {
  "${REST[@]}" --profile tools down -v >/dev/null 2>&1
  docker volume rm -f $VOL >/dev/null 2>&1
}
trap cleanup EXIT
cleanup

echo "Setup"
"${LIVE[@]}" --profile tools build backup >/dev/null 2>&1 || { echo "could not build the backup tool"; exit 2; }
"${LIVE[@]}" ps --format '{{.Service}}' | grep -q '^postgres$' || { echo "The live stack is not running (docker compose up -d)"; exit 2; }
docker volume create $VOL >/dev/null
docker run --rm -v $VOL:/backups --entrypoint sh ragconsumer-backup -c 'age-keygen -o /backups/identity.txt 2>/dev/null; age-keygen -o /backups/other.txt 2>/dev/null; age-keygen -y /backups/identity.txt > /backups/recipient.txt; age-keygen -y /backups/other.txt > /backups/other-recipient.txt'
RECIPIENT="$(docker run --rm -v $VOL:/backups --entrypoint cat ragconsumer-backup /backups/recipient.txt)"
export BACKUP_AGE_RECIPIENT="$RECIPIENT"

echo "Refusals when set up wrongly"
refuse "no recipient key: refuses" "BACKUP_AGE_RECIPIENT is not set" "${LIVE[@]}" --profile tools run --rm -T -e BACKUP_AGE_RECIPIENT= -v $VOL:/backups backup backup
refuse "no off-server destination: refuses" "No off-server destination" "${LIVE[@]}" --profile tools run --rm -T -v $VOL:/backups backup backup

echo "Backup of the live stack"
"${LIVE[@]}" --profile tools run --rm -T -e BACKUP_ALLOW_LOCAL_ONLY=true -v $VOL:/backups backup backup >/dev/null && ok "backup completes" || bad "backup failed"
NAME="$(docker run --rm -v $VOL:/backups --entrypoint sh ragconsumer-backup -c 'ls /backups | grep "^ragconsumer-.*tar.age$" | head -1')"
[[ -n "$NAME" ]] && ok "an encrypted backup file exists ($NAME)" || { bad "no backup file"; exit 1; }
check "the file is not readable without the key (no plain tar/zip/pg header)" docker run --rm -v $VOL:/backups --entrypoint sh ragconsumer-backup -c "head -c 40 /backups/$NAME | grep -q 'age-encryption.org'"
check "the data is not visible inside the file" docker run --rm -v $VOL:/backups --entrypoint sh ragconsumer-backup -c "! grep -qa 'PGDMP' /backups/$NAME"

echo "Empty restore target"
"${REST[@]}" up -d --wait postgres minio qdrant >/dev/null 2>&1 && ok "scratch data stores are up" || { bad "scratch stores did not start"; exit 1; }
[[ "$(psqlx REST "select count(*) from information_schema.tables where table_schema='public'")" == "0" ]] && ok "the target database starts empty" || bad "target not empty"

echo "Ways a restore can go wrong (nothing may change)"
refuse "no confirmation flag: refuses" "OVERWRITES" tool REST restore "$NAME" --identity /backups/identity.txt
refuse "wrong private key: refuses" "could not decrypt" tool REST restore "$NAME" --identity /backups/other.txt --yes-overwrite
docker run --rm -v $VOL:/backups --entrypoint sh ragconsumer-backup -c "cp /backups/$NAME /backups/damaged.tar.age && printf 'X' | dd of=/backups/damaged.tar.age bs=1 seek=2000 conv=notrunc 2>/dev/null"
refuse "damaged file: refuses" "ERROR" tool REST restore damaged.tar.age --identity /backups/identity.txt --yes-overwrite
[[ "$(psqlx REST "select count(*) from information_schema.tables where table_schema='public'")" == "0" ]] && ok "and the target is still untouched" || bad "a failed restore changed the target"

echo "Restore"
tool REST restore "$NAME" --identity /backups/identity.txt --yes-overwrite && ok "restore completes" || bad "restore failed"

echo "Independent comparison, live vs restored"
TABLES="$(psqlx LIVE "select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1")"
same=1
for t in $TABLES; do
  a="$(psqlx LIVE "select count(*) from public.\"$t\"")"; b="$(psqlx REST "select count(*) from public.\"$t\"")"
  [[ "$a" == "$b" ]] || { same=0; echo "    $t: live $a, restored $b"; }
done
[[ $same == 1 && -n "$TABLES" ]] && ok "every table has the same number of rows ($(wc -w <<<"$TABLES") tables)" || bad "table row counts differ"
[[ "$(psqlx LIVE "select md5(string_agg(t::text, '' order by t::text)) from public.users t")" == "$(psqlx REST "select md5(string_agg(t::text, '' order by t::text)) from public.users t")" ]] && ok "user accounts are identical (including password hashes)" || bad "users differ"
[[ "$(psqlx LIVE "select version_num from alembic_version")" == "$(psqlx REST "select version_num from alembic_version")" ]] && ok "same database migration version" || bad "migration versions differ"
out="$("${REST[@]}" exec -T postgres sh -c 'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "delete from audit_log" 2>&1')"
grep -qi "append-only\|not allowed\|cannot\|rejected\|denied" <<<"$out" && ok "audit log rejects deletes again after restore" || bad "audit log delete was NOT rejected after restore: $out"

rest_docs="$("${REST[@]}" --profile tools run --rm -T --entrypoint sh backup -c 'RCLONE_CONFIG_M_TYPE=s3 RCLONE_CONFIG_M_PROVIDER=Minio RCLONE_CONFIG_M_ENDPOINT=http://minio:9000 RCLONE_CONFIG_M_ACCESS_KEY_ID=$MINIO_ROOT_USER RCLONE_CONFIG_M_SECRET_ACCESS_KEY=$MINIO_ROOT_PASSWORD rclone md5sum m:documents | sort' 2>/dev/null)"
live_docs="$("${LIVE[@]}" --profile tools run --rm -T --entrypoint sh backup -c 'RCLONE_CONFIG_M_TYPE=s3 RCLONE_CONFIG_M_PROVIDER=Minio RCLONE_CONFIG_M_ENDPOINT=http://minio:9000 RCLONE_CONFIG_M_ACCESS_KEY_ID=$MINIO_ROOT_USER RCLONE_CONFIG_M_SECRET_ACCESS_KEY=$MINIO_ROOT_PASSWORD rclone md5sum m:documents | sort' 2>/dev/null)"
[[ -n "$live_docs" && "$live_docs" == "$rest_docs" ]] && ok "every stored document has the same checksum ($(wc -l <<<"$live_docs") files)" || bad "stored documents differ"

qsum() { local -n c=$1; "${c[@]}" --profile tools run --rm -T --entrypoint sh backup -c '
  for col in $(curl -sf -H "api-key: $QDRANT_API_KEY" $QDRANT_URL/collections | python3 -c "import sys,json;print(*sorted(c[\"name\"] for c in json.load(sys.stdin)[\"result\"][\"collections\"]))"); do
    echo $col $(curl -sf -H "api-key: $QDRANT_API_KEY" -H "content-type: application/json" -X POST $QDRANT_URL/collections/$col/points/scroll -d "{\"limit\":1000,\"with_payload\":true,\"with_vector\":true}" | python3 -c "
import sys,json,hashlib
pts=sorted(json.load(sys.stdin)[\"result\"][\"points\"], key=lambda p: str(p[\"id\"]))
print(len(pts), hashlib.sha256(json.dumps(pts, sort_keys=True).encode()).hexdigest())")
  done' 2>/dev/null; }
LQ="$(qsum LIVE)"; RQ="$(qsum REST)"
[[ -n "$LQ" && "$LQ" == "$RQ" ]] && ok "search index identical, vectors and text included ($(wc -l <<<"$LQ") collections)" || { bad "search index differs"; echo "$LQ"; echo "$RQ"; }

echo "Off-server copy (scratch MinIO acts as the off-server bucket)"
OFF=(-e BACKUP_S3_BUCKET=offsite -e BACKUP_S3_PROVIDER=Minio -e BACKUP_S3_ENDPOINT=http://minio:9000)
USER_="$("${REST[@]}" exec -T minio printenv MINIO_ROOT_USER)"; PASS_="$("${REST[@]}" exec -T minio printenv MINIO_ROOT_PASSWORD)"
"${REST[@]}" --profile tools run --rm -T --entrypoint sh backup -c "RCLONE_CONFIG_M_TYPE=s3 RCLONE_CONFIG_M_PROVIDER=Minio RCLONE_CONFIG_M_ENDPOINT=http://minio:9000 RCLONE_CONFIG_M_ACCESS_KEY_ID=$USER_ RCLONE_CONFIG_M_SECRET_ACCESS_KEY=$PASS_ rclone mkdir m:offsite" >/dev/null 2>&1
"${REST[@]}" --profile tools run --rm -T -v $VOL:/backups "${OFF[@]}" -e BACKUP_S3_ACCESS_KEY="$USER_" -e BACKUP_S3_SECRET_KEY="$PASS_" -e BACKUP_ALLOW_LOCAL_ONLY=false backup backup >/dev/null 2>&1 && ok "backup with off-server copy completes" || bad "backup with off-server copy failed"
listing="$("${REST[@]}" --profile tools run --rm -T -v $VOL:/backups "${OFF[@]}" -e BACKUP_S3_ACCESS_KEY="$USER_" -e BACKUP_S3_SECRET_KEY="$PASS_" backup list 2>&1)"
[[ "$(grep -c 'ragconsumer-.*tar.age' <<<"$listing")" -ge 3 ]] && ok "list shows the backups here and off the server" || bad "list: $listing"
# remove every local copy, then restore straight from the off-server bucket
docker run --rm -v $VOL:/backups --entrypoint sh ragconsumer-backup -c 'rm -f /backups/ragconsumer-*.tar.age'
latest="$(grep -o 'ragconsumer-[0-9TZ]*\.tar\.age' <<<"$listing" | sort | tail -1)"
"${REST[@]}" --profile tools run --rm -T -v $VOL:/backups "${OFF[@]}" -e BACKUP_S3_ACCESS_KEY="$USER_" -e BACKUP_S3_SECRET_KEY="$PASS_" backup restore "$latest" --identity /backups/identity.txt --yes-overwrite >/dev/null 2>&1 \
  && ok "restore straight from the off-server copy works (no local file needed)" || bad "restore from the off-server copy failed"

echo
if [[ $fail -eq 0 ]]; then echo "BACKUP DRILL PASSED"; else echo "BACKUP DRILL FAILED"; fi
exit $fail
