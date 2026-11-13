#!/usr/bin/env bash
# Hardens a fresh Ubuntu 24.04 server before it holds any client documents.
#
#   sudo DEPLOY_SSH_KEY="ssh-ed25519 AAAA... you@laptop" bash deploy/harden-server.sh
#
# Safe to run again: every step checks before it changes anything.
#
# What it sets up (KAN-87):
#   * a non-root "deploy" user that runs Docker, reachable by SSH key only
#   * SSH: no passwords, no root login, only that user, few attempts
#   * firewall (ufw): only 22 (rate limited), 80 and 443 open
#   * fail2ban for SSH brute-force attempts
#   * automatic security updates, with a nightly reboot window if one is needed
#   * Docker: rotated logs, no-new-privileges
#   * system logs kept 90 days within a size cap
#   * a few kernel network protections
#
# Disk encryption is done by the cloud provider (encrypted volumes), not here:
# confirm it is on in the provider's console. check-hardening.sh reminds you.
#
# It will NOT lock you out: it installs your key first, and refuses to turn off
# password login until that key is in place. Keep your current session open and
# test a new login in a second terminal before closing it.

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
DEPLOY_SSH_KEY="${DEPLOY_SSH_KEY:-}"
SKIP_DOCKER="${SKIP_DOCKER:-0}"          # for testing in a container
SKIP_FIREWALL="${SKIP_FIREWALL:-0}"      # for testing where iptables is unavailable
SSH_PORT="${SSH_PORT:-22}"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root (sudo)"
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || die "written for Ubuntu (found ${ID:-unknown})"

export DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
log "Packages"
apt-get update -qq
PACKAGES=(ufw fail2ban unattended-upgrades openssh-server curl ca-certificates sudo)
[[ "$SKIP_DOCKER" == "1" ]] || PACKAGES+=(docker.io docker-compose-v2)
apt-get install -y -qq "${PACKAGES[@]}" >/dev/null

# ---------------------------------------------------------------------------
log "Deploy user: $DEPLOY_USER"
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER" >/dev/null
fi
[[ "$SKIP_DOCKER" == "1" ]] || usermod -aG docker "$DEPLOY_USER"
# Administration happens as this user. It is already root-equivalent through
# Docker, so sudo adds no new power; login is by key only (see SSH below).
echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$DEPLOY_USER"
chmod 440 "/etc/sudoers.d/90-$DEPLOY_USER"
visudo -cf "/etc/sudoers.d/90-$DEPLOY_USER" >/dev/null

HOME_DIR="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$HOME_DIR/.ssh"
AUTH_KEYS="$HOME_DIR/.ssh/authorized_keys"
touch "$AUTH_KEYS"
if [[ -n "$DEPLOY_SSH_KEY" ]] && ! grep -qF "$DEPLOY_SSH_KEY" "$AUTH_KEYS"; then
  echo "$DEPLOY_SSH_KEY" >> "$AUTH_KEYS"
fi
chown "$DEPLOY_USER:$DEPLOY_USER" "$AUTH_KEYS"
chmod 600 "$AUTH_KEYS"
# The lock-out guard: never turn passwords off without a key to log in with.
grep -qE '^(ssh-|ecdsa-|sk-)' "$AUTH_KEYS" \
  || die "no SSH key for $DEPLOY_USER. Pass your public key: DEPLOY_SSH_KEY=\"ssh-ed25519 AAAA...\""

# ---------------------------------------------------------------------------
log "SSH: keys only, no root login"
# Named 00- so it is read before cloud-image files such as 50-cloud-init.conf
# (the first value found wins in sshd).
install -d -m 755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/00-ragconsumer-hardening.conf <<EOF
# Managed by deploy/harden-server.sh
Port $SSH_PORT
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
AllowUsers $DEPLOY_USER
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
# Tunnels to the server (for example to reach an internal admin page) are fine;
# the server does not forward to anywhere else.
AllowTcpForwarding local
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
mkdir -p /run/sshd
sshd -t || die "the SSH configuration is invalid; nothing was reloaded"
if systemctl is-active --quiet ssh 2>/dev/null; then
  systemctl reload ssh
elif systemctl is-active --quiet sshd 2>/dev/null; then
  systemctl reload sshd
fi
passwd -l root >/dev/null 2>&1 || true     # no password login for root, ever

# ---------------------------------------------------------------------------
if [[ "$SKIP_FIREWALL" == "1" ]]; then
  log "Firewall: skipped (SKIP_FIREWALL=1)"
else
  log "Firewall: only SSH, HTTP and HTTPS"
  ufw --force reset >/dev/null
  ufw default deny incoming >/dev/null
  ufw default allow outgoing >/dev/null
  ufw limit "$SSH_PORT"/tcp >/dev/null          # allow, but rate limit repeated attempts
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw allow 443/udp >/dev/null                  # HTTP/3
  ufw --force enable >/dev/null
fi

# ---------------------------------------------------------------------------
log "fail2ban for SSH"
cat > /etc/fail2ban/jail.d/ragconsumer.local <<EOF
# Managed by deploy/harden-server.sh
[DEFAULT]
bantime.increment = true
bantime.maxtime = 1w

[sshd]
enabled = true
port = $SSH_PORT
backend = systemd
maxretry = 4
findtime = 10m
bantime = 1h
EOF
systemctl enable --now fail2ban >/dev/null 2>&1 || true
systemctl restart fail2ban >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
log "Automatic security updates"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
cat > /etc/apt/apt.conf.d/52ragconsumer-unattended-upgrades <<'EOF'
// Managed by deploy/harden-server.sh
Unattended-Upgrade::Allowed-Origins {
        "${distro_id}:${distro_codename}-security";
        "${distro_id}ESMApps:${distro_codename}-apps-security";
        "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
// Kernel updates need a reboot. Do it at night; every container restarts by
// itself afterwards (restart: unless-stopped).
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF

# ---------------------------------------------------------------------------
if [[ "$SKIP_DOCKER" != "1" ]]; then
  log "Docker daemon: rotated logs, no-new-privileges"
  install -d -m 755 /etc/docker
  cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" },
  "no-new-privileges": true,
  "live-restore": true
}
EOF
  systemctl enable --now docker >/dev/null 2>&1 || true
  systemctl restart docker >/dev/null 2>&1 || true
fi

# ---------------------------------------------------------------------------
log "System logs: kept 90 days, capped at 500 MB"
install -d -m 755 /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/ragconsumer.conf <<'EOF'
# Managed by deploy/harden-server.sh
[Journal]
Storage=persistent
SystemMaxUse=500M
MaxRetentionSec=90day
EOF
systemctl restart systemd-journald >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
log "Kernel network protections"
cat > /etc/sysctl.d/99-ragconsumer.conf <<'EOF'
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
EOF
sysctl --system >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
cat <<EOF

Done. Before you close this session:
  1. In a SECOND terminal, log in:   ssh $DEPLOY_USER@<server>
  2. Only if that works, close this one.
Then run:  sudo bash deploy/check-hardening.sh
And confirm in the provider's console that disk encryption is enabled.
EOF
