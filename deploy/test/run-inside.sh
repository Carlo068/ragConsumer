#!/usr/bin/env bash
# Runs INSIDE the throwaway test machine (started by deploy/test-hardening.sh).
# Hardens it, then proves the controls really work by trying to break them.
set -u
cd /root
fail=0
ok()  { printf '  PASS  %s\n' "$1"; }
bad() { printf '  FAIL  %s\n' "$1"; fail=1; }
expect() { # expect "description" "expected substring" command...
  local what="$1" want="$2"; shift 2
  local out; out="$("$@" 2>&1)"
  if grep -qF -- "$want" <<<"$out"; then ok "$what"; else bad "$what (got: $(head -c 120 <<<"$out"))"; fi
}
SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o LogLevel=ERROR"

echo "Lock-out guard"
rm -f /etc/ssh/sshd_config.d/00-ragconsumer-hardening.conf
out="$(SKIP_DOCKER=1 bash deploy/harden-server.sh 2>&1)"; code=$?
[[ $code -ne 0 ]] && ok "refuses to run without an SSH key" || bad "ran without an SSH key"
[[ ! -e /etc/ssh/sshd_config.d/00-ragconsumer-hardening.conf ]] && ok "and changed nothing about SSH" || bad "wrote the SSH config before the guard"

echo "Hardening"
ssh-keygen -q -t ed25519 -N '' -f /root/id
SKIP_DOCKER=1 DEPLOY_SSH_KEY="$(cat /root/id.pub)" bash deploy/harden-server.sh >/dev/null 2>&1 && ok "hardening script succeeds" || bad "hardening script failed"
SKIP_DOCKER=1 DEPLOY_SSH_KEY="$(cat /root/id.pub)" bash deploy/harden-server.sh >/dev/null 2>&1 && ok "and can be run again" || bad "second run failed"
[[ "$(grep -c "$(cut -d' ' -f2 /root/id.pub)" /home/deploy/.ssh/authorized_keys)" == 1 ]] && ok "the key is installed once, not duplicated" || bad "key duplicated"

systemctl start ssh; sleep 2
echo "Who can log in"
expect "deploy with its key can log in"              "logged-in-as deploy" $SSH -i /root/id deploy@localhost 'echo logged-in-as $(whoami)'
expect "deploy with a password is refused"           "Permission denied (publickey)" $SSH -o PreferredAuthentications=password -o PubkeyAuthentication=no -o BatchMode=yes deploy@localhost true
mkdir -p /root/.ssh; cat /root/id.pub >> /root/.ssh/authorized_keys
expect "root is refused even with a valid key"       "Permission denied" $SSH -i /root/id root@localhost true
useradd -m other 2>/dev/null; install -d -m 700 -o other /home/other/.ssh; cp /root/id.pub /home/other/.ssh/authorized_keys; chown other /home/other/.ssh/authorized_keys; chmod 600 /home/other/.ssh/authorized_keys
expect "another user is refused even with a valid key" "Permission denied" $SSH -i /root/id other@localhost true
expect "deploy can administer the server (sudo)"     "sudo-ok" $SSH -i /root/id deploy@localhost 'sudo -n true && echo sudo-ok'

echo "Firewall"
ufw status | grep -q "Status: active" && ok "ufw is active" || bad "ufw is not active"
expect "SSH is rate limited"       "22/tcp                     LIMIT" ufw status
expect "HTTPS is open"             "443/tcp                    ALLOW" ufw status
ufw status | grep -qE '^(5432|8000|9000|6333)' && bad "an internal port is open" || ok "no internal port is open"

echo "Audit script"
SKIP_DOCKER=1 bash deploy/check-hardening.sh >/dev/null 2>&1 && ok "passes on the hardened machine" || bad "fails on the hardened machine"
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config.d/00-ragconsumer-hardening.conf
SKIP_DOCKER=1 bash deploy/check-hardening.sh >/dev/null 2>&1 && bad "did not notice password login being turned on" || ok "notices password login being turned on"
sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config.d/00-ragconsumer-hardening.conf
ufw allow 5432/tcp >/dev/null
SKIP_DOCKER=1 bash deploy/check-hardening.sh >/dev/null 2>&1 && bad "did not notice an extra open port" || ok "notices an extra open port"
ufw delete allow 5432/tcp >/dev/null
SKIP_DOCKER=1 bash deploy/check-hardening.sh >/dev/null 2>&1 && ok "passes again once fixed" || bad "still failing after the fix"

echo "Backup timer"
printf '#!/bin/sh
exit 0
' > /usr/bin/docker; chmod +x /usr/bin/docker
printf '[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
' > /etc/systemd/system/docker.service; systemctl daemon-reload  # stand-in: the test machine has no Docker
mkdir -p /home/deploy/ragConsumer; cp -r /root/deploy /home/deploy/ragConsumer/deploy
bash deploy/install-backup-timer.sh >/dev/null 2>&1 && ok "backup timer installs" || bad "backup timer failed to install"
bash deploy/install-backup-timer.sh >/dev/null 2>&1 && ok "and can be installed again" || bad "second install failed"
systemctl is-enabled ragconsumer-backup.timer >/dev/null 2>&1 && ok "the timer is enabled" || bad "timer not enabled"
systemctl is-active ragconsumer-backup.timer >/dev/null 2>&1 && ok "and scheduled (survives reboots, catches up if the server was off)" || bad "timer not active"
[[ -z "$(systemd-analyze verify /etc/systemd/system/ragconsumer-backup.service /etc/systemd/system/ragconsumer-backup.timer 2>&1)" ]] && ok "systemd finds nothing wrong with the units" || bad "systemd-analyze reports problems: $(systemd-analyze verify /etc/systemd/system/ragconsumer-backup.service /etc/systemd/system/ragconsumer-backup.timer 2>&1 | head -3)"
systemctl start ragconsumer-backup.service >/dev/null 2>&1 && ok "running it by hand works (stub docker)" || bad "service run failed"

echo "Monitor timer and logs"
bash deploy/install-monitor-timer.sh >/dev/null 2>&1 && ok "monitor timer installs" || bad "monitor timer failed to install"
systemctl is-active ragconsumer-monitor.timer >/dev/null 2>&1 && ok "and runs every few minutes" || bad "monitor timer not active"
[[ -z "$(systemd-analyze verify /etc/systemd/system/ragconsumer-monitor.service /etc/systemd/system/ragconsumer-monitor.timer 2>&1)" ]] && ok "systemd finds nothing wrong with the monitor units" || bad "monitor units: $(systemd-analyze verify /etc/systemd/system/ragconsumer-monitor.service /etc/systemd/system/ragconsumer-monitor.timer 2>&1 | head -3)"
[[ "$(journalctl --disk-usage 2>/dev/null | wc -l)" -ge 1 && -f /etc/systemd/journald.conf.d/ragconsumer.conf ]] && ok "system logs have a size and age limit" || bad "journald limits missing"
sed -i 's/^MaxRetentionSec=90day/MaxRetentionSec=1day/' /etc/systemd/journald.conf.d/ragconsumer.conf
SKIP_DOCKER=1 bash deploy/check-hardening.sh >/dev/null 2>&1 && bad "did not notice the log retention being shortened" || ok "notices the log retention being changed"
sed -i 's/^MaxRetentionSec=1day/MaxRetentionSec=90day/' /etc/systemd/journald.conf.d/ragconsumer.conf

echo
if [[ $fail -eq 0 ]]; then echo "HARDENING TESTS PASSED"; else echo "HARDENING TESTS FAILED"; fi
exit $fail
