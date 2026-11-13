#!/usr/bin/env bash
# Checks that the server is still hardened, and prints PASS or FAIL for each
# control. Exits non-zero if anything fails, so it can run from a scheduler.
#
#   sudo bash deploy/check-hardening.sh
#
# Run it after hardening, after every deploy, and now and then in between.

DEPLOY_USER="${DEPLOY_USER:-deploy}"
SKIP_DOCKER="${SKIP_DOCKER:-0}"
SKIP_FIREWALL="${SKIP_FIREWALL:-0}"
ENV_FILE="${ENV_FILE:-/home/$DEPLOY_USER/ragConsumer/.env}"

failed=0
pass() { printf '  PASS  %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; failed=1; }
check() { # check "description" command...
  local what="$1"; shift
  if "$@" >/dev/null 2>&1; then pass "$what"; else fail "$what"; fi
}
sshd_has() { sshd -T 2>/dev/null | grep -qix "$1"; }

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 2; }

echo "SSH"
check "root cannot log in over SSH"        sshd_has "permitrootlogin no"
check "password login is off"              sshd_has "passwordauthentication no"
check "keyboard-interactive login is off"  sshd_has "kbdinteractiveauthentication no"
check "only $DEPLOY_USER may log in"       sshd_has "allowusers $DEPLOY_USER"
check "at most 3 attempts per connection"  sshd_has "maxauthtries 3"
check "$DEPLOY_USER has an SSH key installed" grep -qE '^(ssh-|ecdsa-|sk-)' "/home/$DEPLOY_USER/.ssh/authorized_keys"
check "the root password is locked"        bash -c "passwd -S root | awk '{print \$2}' | grep -qE '^(L|LK)$'"

echo "Accounts"
check "$DEPLOY_USER is not root (uid != 0)" bash -c "[ \"\$(id -u $DEPLOY_USER)\" != 0 ]"
if [[ "$SKIP_DOCKER" != "1" ]]; then
  check "only $DEPLOY_USER is in the docker group" bash -c "[ \"\$(getent group docker | cut -d: -f4)\" = \"$DEPLOY_USER\" ]"
fi

echo "Firewall"
if [[ "$SKIP_FIREWALL" == "1" ]]; then
  echo "  SKIP  firewall checks (SKIP_FIREWALL=1)"
else
  check "ufw is active"                    bash -c "ufw status | grep -q '^Status: active'"
  check "incoming is denied by default"    bash -c "ufw status verbose | grep -q 'deny (incoming)'"
  open_ports="$(ufw status | awk '/ALLOW|LIMIT/ {print $1}' | sed 's#(v6)##' | sort -u | tr '\n' ' ')"
  check "only 22, 80 and 443 are open (found: ${open_ports:-none})" \
    bash -c "echo '$open_ports' | tr ' ' '\n' | grep -v '^$' | grep -vxE '22/tcp|80/tcp|443/tcp|443/udp|22|80|443' | wc -l | grep -qx 0"
fi

echo "Brute-force protection and updates"
check "fail2ban is running"                systemctl is-active --quiet fail2ban
check "fail2ban guards sshd"               bash -c "fail2ban-client status sshd | grep -q 'Status for the jail: sshd'"
check "automatic security updates are on"  bash -c "apt-config dump | grep -q 'APT::Periodic::Unattended-Upgrade \"1\"'"
check "automatic updates are limited to security sources" grep -q 'security' /etc/apt/apt.conf.d/52ragconsumer-unattended-upgrades

if [[ "$SKIP_DOCKER" != "1" ]]; then
  echo "Docker"
  check "container logs are rotated"       bash -c "grep -q '\"max-size\"' /etc/docker/daemon.json"
  check "no-new-privileges is the default" bash -c "grep -q '\"no-new-privileges\": true' /etc/docker/daemon.json"
  published="$(docker ps --format '{{.Ports}}' 2>/dev/null | grep -o '0\.0\.0\.0:[0-9]*->' | sed 's/0\.0\.0\.0://;s/->//' | sort -u | tr '\n' ' ')"
  check "containers publish only ports 80 and 443 to the world (found: ${published:-none})" \
    bash -c "echo '$published' | tr ' ' '\n' | grep -v '^$' | grep -vxE '80|443' | wc -l | grep -qx 0"
  check "databases and internal services publish nothing to the world" \
    bash -c "! docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'postgres|minio|qdrant|backend|worker|mcp' | grep -q '0\.0\.0\.0'"
fi

echo "Secrets file"
if [[ -f "$ENV_FILE" ]]; then
  mode="$(stat -c '%a' "$ENV_FILE")"; owner="$(stat -c '%U' "$ENV_FILE")"
  check ".env is readable only by $DEPLOY_USER (mode $mode, owner $owner)" \
    bash -c "[ '$mode' = 600 ] && [ '$owner' = '$DEPLOY_USER' ]"
else
  echo "  SKIP  no .env at $ENV_FILE yet"
fi

echo
echo "Reminder (cannot be checked from inside the server): disk encryption at rest"
echo "must be enabled for every volume in the cloud provider's console."

echo
if [[ $failed -eq 0 ]]; then echo "ALL HARDENING CHECKS PASSED"; else echo "SOME HARDENING CHECKS FAILED"; fi
exit $failed
