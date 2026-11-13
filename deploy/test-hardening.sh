#!/usr/bin/env bash
# Tests deploy/harden-server.sh and deploy/check-hardening.sh on a throwaway
# Ubuntu machine with real systemd (a privileged container), by hardening it
# and then trying to get in the ways an attacker would.
#
#   bash deploy/test-hardening.sh
#
# Needs Docker. Touches nothing outside the throwaway container.
set -euo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1   # Git Bash on Windows must not rewrite /sys paths

NAME=ragconsumer-hardening-test
docker build -q -t ragconsumer-hardening-test deploy/test >/dev/null
docker rm -f "$NAME" >/dev/null 2>&1 || true
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

docker run -d --name "$NAME" --privileged --cgroupns=host \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw ragconsumer-hardening-test >/dev/null
for _ in $(seq 1 30); do
  state="$(docker exec "$NAME" systemctl is-system-running 2>/dev/null || true)"
  [[ "$state" == "running" || "$state" == "degraded" ]] && break
  sleep 1
done

docker cp deploy "$NAME":/root/deploy
docker exec "$NAME" bash /root/deploy/test/run-inside.sh
