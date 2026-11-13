#!/usr/bin/env bash
# Runs ragConsumer's checks and prints a pass/fail summary. Exits non-zero if
# any check fails.
#   bash .claude/skills/run-checks/run-checks.sh            # code checks only
#   bash .claude/skills/run-checks/run-checks.sh --stack    # also check the running Docker stack
#   PYTEST_ARGS="-k mcp" bash .../run-checks.sh             # pass extra args to pytest

# Repo root is three levels up from this script (.claude/skills/<name>/), so
# it works regardless of the caller's working directory.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CHECK_STACK=0
[[ "${1:-}" == "--stack" ]] && CHECK_STACK=1

declare -a NAMES RESULTS
record() { NAMES+=("$1"); RESULTS+=("$2"); }

run() {  # run <name> <command...> -- prints the output's tail, records PASS/FAIL
  local name="$1"; shift
  echo "===== $name"
  local out
  out="$("$@" 2>&1)"; local code=$?
  echo "$out" | grep -vE "^npm notice" | tail -8
  if [[ $code -eq 0 ]]; then record "$name" PASS; else record "$name" "FAIL (exit $code)"; fi
}

backend_tests() {
  cd "$ROOT/backend" || return 1
  # Activation must happen in the same shell as pytest: without it, the
  # global Python gets used and imports fail confusingly.
  [[ -f .venv/Scripts/activate ]] || { echo "backend/.venv missing -- create it and pip install -r requirements.txt"; return 1; }
  source .venv/Scripts/activate && python -m pytest -q ${PYTEST_ARGS:-}
}
# mcp_server and ingestion_worker have no host virtualenv (their embedding models
# are heavy), so their tests run in their own images with the tests mounted in
# and pytest installed.
service_tests() {
  local svc="$1" compose_service="$2"
  cd "$ROOT" || return 1
  local w; w="$(pwd -W 2>/dev/null || pwd)"
  MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps     -v "$w/$svc/__tests__:/app/__tests__" -v "$w/$svc/pytest.ini:/app/pytest.ini"     --entrypoint sh "$compose_service" -c "pip install -q pytest >/dev/null 2>&1; python -m pytest -q"
}
frontend_typecheck() { cd "$ROOT/frontend" && npx tsc -b; }
frontend_tests()     { cd "$ROOT/frontend" && npx vitest run; }
frontend_lint()      { cd "$ROOT/frontend" && npx oxlint; }   # warnings don't fail; errors do

run "backend pytest"      backend_tests
run "mcp_server pytest"    service_tests mcp_server mcp_server
run "worker pytest"        service_tests ingestion_worker ingestion-worker
run "backup retention"     bash -c "cd \"$ROOT/deploy/backup\" && python -m unittest -q test_retention"
run "frontend tsc"        frontend_typecheck
run "frontend vitest"     frontend_tests
run "frontend oxlint"     frontend_lint

if [[ $CHECK_STACK -eq 1 ]]; then
  echo "===== docker stack"
  (cd "$ROOT" && docker compose ps --format "table {{.Service}}\t{{.Status}}")
  for target in "frontend http://127.0.0.1:5173/" "backend http://127.0.0.1:8000/" "ingestion-worker http://127.0.0.1:8001/health"; do
    set -- $target
    code="$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$2")"
    if [[ "$code" == "200" ]]; then record "stack: $1" PASS; else record "stack: $1" "FAIL (HTTP $code)"; fi
  done

  # Qdrant's own matter isolation, proven live (see mcp_server/app/isolation_check.py).
  echo "===== qdrant isolation"
  if (cd "$ROOT" && docker compose exec -T mcp_server python -m app.isolation_check); then
    record "stack: qdrant isolation" PASS
  else
    record "stack: qdrant isolation" FAIL
  fi
fi

echo; echo "===== SUMMARY"
failed=0
for i in "${!NAMES[@]}"; do
  printf "  %-24s %s\n" "${NAMES[$i]}" "${RESULTS[$i]}"
  [[ "${RESULTS[$i]}" != PASS ]] && failed=1
done
[[ $failed -eq 0 ]] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $failed
