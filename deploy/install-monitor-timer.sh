#!/usr/bin/env bash
# Installs the health monitor as a systemd timer (every 5 minutes) and sends a
# test alert. Run as root on the server, from the repository (which must be at
# /home/deploy/ragConsumer, or set APP_DIR). Safe to run again.
#   sudo bash deploy/install-monitor-timer.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)."; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${APP_DIR:-/home/deploy/ragConsumer}"
sed "s|^WorkingDirectory=.*|WorkingDirectory=$APP_DIR|" "$HERE/ragconsumer-monitor.service" > /etc/systemd/system/ragconsumer-monitor.service
install -m 644 "$HERE/ragconsumer-monitor.timer" /etc/systemd/system/ragconsumer-monitor.timer
systemctl daemon-reload
systemctl enable --now ragconsumer-monitor.timer
systemctl list-timers ragconsumer-monitor.timer --no-pager
if ! grep -qE '^(ALERT_WEBHOOK_URL|ALERT_NTFY_URL)=.+' "$APP_DIR/.env" 2>/dev/null; then
  echo
  echo "WARNING: no alert destination is set in $APP_DIR/.env (ALERT_WEBHOOK_URL or ALERT_NTFY_URL)."
  echo "The monitor will run but nobody will be told. See docs/deployment/07-monitoring.md."
fi
echo "Installed. Send a test alert with:  sudo -u deploy bash $APP_DIR/deploy/monitor.sh --test"
