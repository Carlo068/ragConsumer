# Staging, deploying and rolling back

The aim: a change reaches the firm's server only after it has run somewhere that
does not matter, can be checked from the outside in one command, and can be taken
back in one command if it misbehaves.

## Two environments

| | Staging | Production |
|---|---|---|
| Purpose | Try every release first | What the firm uses |
| Server | A second, small server with the same hardening (`03-server-hardening.md`) | The main server |
| Address | `staging.yourfirm.mx` (its own `DOMAIN`) | `matters.yourfirm.mx` |
| Secrets | Its own `.env`, made with `generate_env.py`, **never copied from production** | Its own `.env` |
| Data | **Invented documents only.** Never a client's file, never a copy of production data | Real matters |
| Deploys | `bash deploy/deploy.sh` (whatever is in `main`) | `bash deploy/deploy.sh <tag>` (a version that has already run on staging) |

The staging rule that matters: **nothing real goes into staging.** It has the same
code but not the same protections around people, so treat anything uploaded there
as public. Make test accounts with `create_admin.py` and invite testers the normal
way.

If a second server is not in the budget yet, rehearse on a laptop instead:
`bash deploy/test-deploy.sh` (below) runs the full production configuration with a
local certificate. It is a weaker substitute, because it cannot show you problems
with the real domain, certificate, firewall or provider.

## Releasing

1. Work is merged into `main` through pull requests (the checks must pass).
2. **Staging:** on the staging server, `bash deploy/deploy.sh`.
3. Check it by hand (about five minutes):
   - sign in; upload a small PDF to a test matter and wait for "ready";
   - connect an AI assistant on the Connect page and ask a question about it;
   - as an admin, open the audit log and see your own actions in it.
4. **Production:** give the version a name that records what ran on staging, and
   deploy it:
   ```bash
   git tag v2026.11.13 && git push origin v2026.11.13      # on your computer, once staging looks right
   bash deploy/deploy.sh v2026.11.13                       # on the production server
   ```
   Deploy outside working hours: the services restart, so people are cut off for
   about one to two minutes.

## What `deploy.sh` does

Run on the server as `deploy`, from the repository. Add `--dry-run` first to see
the plan without changing anything.

1. **Checks before touching anything.** The server's copy has no uncommitted
   edits (it must run exactly what is in git), and the version is in `main` (only
   merged, reviewed work is deployed).
2. **Shows what changes:** the commits, and any **database changes** (migrations).
3. **Takes a backup first** (`05-backups.md`). If the backup fails, nothing is
   deployed. (`SKIP_BACKUP=1` exists for staging only.)
4. Switches the code, rebuilds, restarts.
5. **Checks it from outside** (`deploy/smoke-test.sh`): the web app loads, the API
   answers and refuses strangers, API docs are off, the AI connection refuses a
   request with no token and publishes its sign-in details, HSTS and the content
   security policy are present, plain HTTP redirects to HTTPS; and every service,
   including the ingestion worker, is running. It waits up to 15 minutes, because
   the search models take minutes to load the first time (they are kept in a
   volume afterwards).
6. **If any of that fails, puts the previous version back by itself** and says so.
   The new version is then *not* deployed, and the exit status is non-zero.

Every step is written to `.deploy/history.log`.

You can run the outside check alone, any time: `bash deploy/smoke-test.sh https://matters.yourfirm.mx`.

## Rolling back

```bash
bash deploy/deploy.sh --rollback
```

This puts back the version that was running before the last deploy, and runs the
same outside check. Use it when a release passes the checks but turns out to be
wrong (a feature broken, a wrong behaviour reported by users).

### Database changes and rollback

Rollback changes the **code**, not the data. For that to be safe, **every database
migration must be additive**: new tables, new nullable columns, new indexes.
Never rename or drop something in the same release that stops using it; do that in
a *later* release, once the new one has proven itself. Then the old code keeps
working on the newer database. The backend knows this: if it starts and finds the
database is ahead of it (a rolled-back release), it starts anyway instead of
refusing; any other migration problem still stops it.

If a migration itself did damage (wrong data written, a column filled badly),
rolling back the code does not help; **restore the backup** that was taken just
before the deploy (`05-backups.md`). That loses what was entered after the deploy,
which is why deploys happen out of hours.

### If a rollback fails

`deploy.sh` says so and stops. Then, on the server:

1. `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` and
   `... logs --tail=100 backend` (or whichever service is down) say what is wrong.
2. Put a known good version back by hand:
   `git checkout --detach <commit>` then
   `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
   Good commits are in `.deploy/history.log`.
3. If the data itself is damaged, restore from the last backup (`05-backups.md`).

## Rehearsing the process

`bash deploy/test-deploy.sh` builds a scratch copy of the whole stack and runs the
real scripts through: a first deploy; a good release with a database migration; a
deliberately broken release that must roll back by itself; a manual rollback
across the migration; and the refusals (uncommitted edits, a commit not in `main`,
a failing backup, nothing to do). It touches nothing outside its own scratch
containers. Run it after changing anything under `deploy/` or the backend's start
script.
