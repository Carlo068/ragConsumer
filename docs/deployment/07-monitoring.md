# Monitoring, alerts and logs

A server that nobody is watching fails quietly: the disk fills, a backup stops, a
certificate lapses, and the first person to find out is a lawyer with a deadline.
This sets up a check every five minutes that tells the right people when
something is wrong, and again when it is fixed.

## What is watched

`deploy/monitor.sh` runs every 5 minutes on the server and checks:

| Check | Problem it catches |
|---|---|
| Every service is running, none restarting repeatedly, none killed for lack of memory | A crashed or crash-looping component |
| The document worker answers | Uploads would be accepted but never indexed |
| The site works **from outside** (the same test a deploy uses: web app, API, refusals, AI connection, HTTPS headers) | DNS, certificate, proxy or application failure |
| Disk below 85% | A full disk stops the database and uploads |
| A successful backup in the last 26 hours | The nightly backup silently stopped (`05-backups.md`) |
| HTTPS certificate valid for more than 14 days | Automatic renewal broke |
| No document waiting or processing for over 90 minutes without progress, and none failed for a system reason (`unexpected`, `timed_out`, `index_outdated`) in the last 24 hours | A worker that is up but stuck, a backlog, or an index that needs rebuilding. A scanned or empty file failing is the file's fault and does not alert |

It alerts **when the set of problems changes**, not every five minutes: one
message when something breaks, a reminder every 6 hours while it stays broken, and
a "RECOVERED" message when it is fixed. While anything is wrong the check exits
with an error, so `systemctl --failed` also shows it.

## Setting it up

1. **Choose where alerts go** (put it in `.env`; one or both):
   - `ALERT_WEBHOOK_URL`: an incoming webhook for Slack, Mattermost, Microsoft
     Teams or Discord. Create it in the chat tool's integration settings.
   - `ALERT_NTFY_URL`: an [ntfy](https://ntfy.sh) topic for phone notifications.
     Use a long random topic name, because anyone who knows it can read the alerts.

   Alerts say what is wrong in plain words and never contain document contents,
   names of clients or secrets.

2. **Install the timer** (on the server, as root):
   ```bash
   sudo bash deploy/install-monitor-timer.sh
   ```
   It warns if no alert destination is configured, because then it would run
   without telling anyone.

3. **Send a test alert and check someone receives it:**
   ```bash
   bash deploy/monitor.sh --test
   ```

4. **Cover the one thing the server cannot report: the server itself being down.**
   A free outside service (healthchecks.io, Better Stack, UptimeRobot) is enough:
   - Create a "heartbeat" check there and put its URL in `.env` as
     `HEARTBEAT_URL`. The monitor pings it after every fully healthy run; if the
     pings stop, that service alerts you, whatever state the server is in.
   - Optionally also let the service request `https://matters.yourfirm.mx/` every
     few minutes.

   Neither sends anything about your data: they only see that an address answered.

## When an alert arrives

| Alert says | What it means and what to do |
|---|---|
| `service X is not running` / `keeps restarting` | `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 X`. After a deploy, `bash deploy/deploy.sh --rollback` (`06-deploy-and-rollback.md`). |
| `killed for lack of memory` | The server is too small for the search models. Use a bigger plan (`01-provider-options.md`). |
| `the document worker does not answer` | Uploads are not being indexed. Same as above for the `ingestion-worker` service. |
| `the site fails its outside check: ...` | The list says which part. Often the certificate, DNS, or a service from the rows above. Run `bash deploy/smoke-test.sh https://your.domain` for the full picture. |
| `the disk is N% full` | `docker system df` and `df -h`. Old images: `docker image prune -a`. Otherwise grow the volume at the provider. Do not delete anything under `/var/lib/docker/volumes` by hand. |
| `no successful backup` / `last successful backup was N hours ago` | `journalctl -u ragconsumer-backup.service -n 50`, then run a backup by hand (`05-backups.md`). Most often the off-server bucket's key or space. |
| `the HTTPS certificate expires in N days` | Caddy renews on its own at 30 days. Failing means it cannot: check DNS still points here and ports 80/443 are open, `docker compose ... logs caddy`. |
| `N document(s) have been waiting or processing...` | The worker is alive but not finishing documents. `docker compose ... logs --tail=200 ingestion-worker`; restarting it (`docker compose ... restart ingestion-worker`) puts in-flight documents back in the queue. |
| `N document(s) failed because of the system...` | See the failure reason on the document in the app. `index_outdated` means the search models changed: `docker compose exec backend python scripts/reindex_all.py --yes`. |
| `RECOVERED` | Nothing to do. |

## Logs: what is kept, where, and for how long

| Log | Holds | Kept | How to read it |
|---|---|---|---|
| **Audit log** (in the application) | Who signed in, uploaded, deleted, shared, used the AI connection, exported or viewed the log itself | Permanently; the database rejects any edit or deletion, so not even an administrator can change it through the application | Admin page in the app, or its CSV export |
| **Web access log** (Caddy) | Every request: time, address, path, status. Invitation tokens and `Referer` are scrubbed; credentials are never written | 90 days (40 files of up to 50 MB; oldest removed first) | `docker compose ... exec caddy cat /var/log/caddy/access.log` |
| **System log** (journald) | SSH logins, firewall and fail2ban bans, backup and monitor runs, reboots | 90 days, at most 500 MB (set by `harden-server.sh`) | `journalctl -u ragconsumer-backup.service`, `journalctl -u ssh`, ... |
| **Application logs** (Docker) | Errors and start-up messages from each service | A few days (10 MB × 5 files per service) | `docker compose ... logs --tail=200 backend` |

If a log is needed as evidence of an incident, copy it out before the retention
runs out; for anything involving client data, the audit log is the record.

## Proving it works

`bash deploy/test-deploy.sh` includes a monitoring rehearsal on a scratch stack: a
healthy server alerts no one and pings the heartbeat; a stopped worker produces
exactly one alert that names it (not one per run) and no heartbeat; recovery sends
one "RECOVERED"; a full disk, a stale backup and a missing backup record are each
detected; the test alert is delivered; with no channel configured the monitor says
nobody was told; and the access log is shown to contain no invitation token.
`deploy/test-hardening.sh` checks the timer units and the log limits.
