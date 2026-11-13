#!/usr/bin/env bash
# Checks a deployed copy from the OUTSIDE, the way a person's browser and AI
# assistant reach it: through the one HTTPS address.
#
#   bash deploy/smoke-test.sh https://matters.yourfirm.mx
#   SMOKE_INSECURE=1 bash deploy/smoke-test.sh https://localhost    # local test certificate
#
# Exits 0 when everything answers as it should, 1 otherwise. Used by
# deploy/deploy.sh after every deploy, and safe to run at any time.
set -uo pipefail
BASE="${1:?usage: smoke-test.sh https://your.domain}"
BASE="${BASE%/}"
CURL=(curl -s --max-time 15)
[[ "${SMOKE_INSECURE:-}" == "1" || "$BASE" == https://localhost* ]] && CURL+=(-k)

fail=0
ok()  { printf '  PASS  %s\n' "$1"; }
bad() { printf '  FAIL  %s\n' "$1"; fail=1; }
code_of() { "${CURL[@]}" -o /dev/null -w '%{http_code}' "$@"; }
expect_code() { # description, expected, url...
  local what="$1" want="$2"; shift 2
  local got; got="$(code_of "$@")"
  [[ "$got" == "$want" ]] && ok "$what" || bad "$what (expected HTTP $want, got $got)"
}

echo "Smoke test of $BASE"
body="$("${CURL[@]}" "$BASE/")"
[[ "$(code_of "$BASE/")" == "200" && "$body" == *'id="root"'* ]] && ok "the web app loads" || bad "the web app does not load"
expect_code "the API answers through the proxy"                "200" "$BASE/api/"
expect_code "the API refuses an unauthenticated request"        "401" "$BASE/api/auth/me"
expect_code "the API documentation is not exposed"              "404" "$BASE/api/docs"
expect_code "the AI connection refuses a request with no token" "401" -X POST "$BASE/mcp" -H 'content-type: application/json' -d '{}'
expect_code "the AI connection publishes its sign-in details"   "200" "$BASE/.well-known/oauth-protected-resource"
headers="$("${CURL[@]}" -I "$BASE/")"
grep -qi '^strict-transport-security' <<<"$headers" && ok "HTTPS is enforced for browsers (HSTS)" || bad "no HSTS header"
grep -qi '^content-security-policy' <<<"$headers" && ok "the content security policy is present" || bad "no content security policy"
if [[ "$BASE" == https://* ]]; then
  [[ "$(code_of "http://${BASE#https://}/")" =~ ^30[1278]$ ]] && ok "plain HTTP is redirected to HTTPS" || bad "plain HTTP is not redirected"
fi

[[ $fail -eq 0 ]] && echo "SMOKE TEST PASSED" || echo "SMOKE TEST FAILED"
exit $fail
