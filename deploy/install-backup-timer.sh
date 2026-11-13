#!/usr/bin/env bash
# Installs the nightly backup as a systemd timer. Run as root on the server,
# from the repository (which must be at /home/deploy/ragConsumer, or set APP_DIR).
#   sudo bash deploy/install-backup-timer.sh
# Safe to run again.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)."; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${APP_DIR:-/home/deploy/ragConsumer}"
sed "s|^WorkingDirectory=.*|WorkingDirectory=$APP_DIR|" "$HERE/ragconsumer-backup.service" > /etc/systemd/system/ragconsumer-backup.service
install -m 644 "$HERE/ragconsumer-backup.timer" /etc/systemd/system/ragconsumer-backup.timer
systemctl daemon-reload
systemctl enable --now ragconsumer-backup.timer
systemctl list-timers ragconsumer-backup.timer --no-pager
echo "Installed. Check the last run with: journalctl -u ragconsumer-backup.service -n 50"
