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
# mcp_server has no host virtualenv (its embedding models are heavy), so its
# tests run in its own image with the tests mounted in and pytest installed.
mcp_tests() {
  cd "$ROOT" || return 1
  local w; w="$(pwd -W 2>/dev/null || pwd)"
  MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps     -v "$w/mcp_server/__tests__:/app/__tests__" -v "$w/mcp_server/pytest.ini:/app/pytest.ini"     --entrypoint sh mcp_server -c "pip install -q pytest >/dev/null 2>&1; python -m pytest -q"
}
frontend_typecheck() { cd "$ROOT/frontend" && npx tsc -b; }
frontend_tests()     { cd "$ROOT/frontend" && npx vitest run; }
frontend_lint()      { cd "$ROOT/frontend" && npx oxlint; }   # warnings don't fail; errors do

run "backend pytest"      backend_tests
run "mcp_server pytest"    mcp_tests
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
fi

echo; echo "===== SUMMARY"
failed=0
for i in "${!NAMES[@]}"; do
  printf "  %-24s %s\n" "${NAMES[$i]}" "${RESULTS[$i]}"
  [[ "${RESULTS[$i]}" != PASS ]] && failed=1
done
[[ $failed -eq 0 ]] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $failed
