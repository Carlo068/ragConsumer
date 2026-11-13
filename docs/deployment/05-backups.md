# Backups and restoring

A server can be lost: a provider failure, a mistake, ransomware. This is how the
firm's data survives that. Every night the system takes an **encrypted backup of
the database, the stored documents and the search index**, copies it **off the
server**, and keeps it for a year. A restore has been tested end to end.

## What is and is not backed up

| Backed up | |
|---|---|
| Postgres | Accounts, matters, who may see what, document records, personal access token hashes, the audit log. |
| MinIO | Every uploaded document. |
| Qdrant | The search index (including the text of each fragment). Restoring it saves re-indexing, which can take hours for a large archive. |

| **Not** backed up | Where it lives instead |
|---|---|
| `.env` (the secrets) | Your password manager, in a secure note. See `04-secrets.md`. Without it a restored server cannot start. |
| The backup **private key** | Your password manager **and** a second place (printed, in a safe). Without it every backup is unreadable, by design. |
| TLS certificates | Caddy obtains them again by itself. |
| Downloaded AI models | Downloaded again on first start. |

How much can be lost: up to one day of work (everything since 02:30 the last
night). Uploads from the morning of a disaster would have to be uploaded again.

## How it protects confidentiality

Backups are encrypted with [age](https://age-encryption.org) to a **public key**
that sits on the server. The matching **private key is not on the server**. So
someone who breaks into the server, or into the backup bucket, gets files they
cannot open, and cannot decrypt older backups. Only restoring needs the private
key.

## Setting it up (once)

1. **Make the key pair, on your own computer or on the server, then keep the
   private part off the server:**

   ```bash
   docker compose --profile tools run --rm --entrypoint age-keygen backup
   ```

   It prints a line `Public key: age1...` and, in the file or on screen, an
   `AGE-SECRET-KEY-...` line. Save the secret line in your password manager and
   in a second safe place, then make sure it is **not** left on the server
   (clear the terminal history). Put the public key in `.env` as
   `BACKUP_AGE_RECIPIENT`.

2. **Create an off-server bucket** at any S3-compatible storage provider
   (Backblaze B2, Wasabi, Hetzner Object Storage, AWS S3, Cloudflare R2...). It
   must be in a **different company or at least a different account and
   location** than the server, so a single failure cannot take both. Create an
   access key limited to that bucket and put the `BACKUP_S3_*` values in `.env`
   (see `.env.example`). Choose a region that fits where the firm may store
   client data (KAN-85 / `01-provider-options.md`).

3. **Switch on the nightly timer** (on the server, as root):

   ```bash
   sudo bash deploy/install-backup-timer.sh
   ```

   It runs at 02:30 server time, catches up if the server was off, and a run is
   cut off after 3 hours.

4. **Run the first backup by hand and look at it:**

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile tools run --rm backup backup
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile tools run --rm backup list
   ```

   The tool refuses to run without an off-server destination, because a backup
   that only exists on the server is lost with it.

## Retention

Every backup for 14 days, then the first of each week for 8 weeks, then the first
of each month for 12 months (so about 34 files at most). The newest backup is
never deleted. A copy of the last 7 also stays on the server for quick restores.
All of it can be changed with `BACKUP_KEEP_*` in `.env`.

**Protection against ransomware:** if someone with the server's keys could also
delete the backups, they would. For stronger protection give the bucket access
key *no delete permission*, turn on the provider's object lock or versioning with
lifecycle rules for the 12-month retention, and set `BACKUP_PRUNE_REMOTE=false`.

## Restoring

Use this when the server is lost, or after a serious mistake (for example a matter
deleted by accident that has to come back).

**On a new server:**

1. Provision and harden it (`03-server-hardening.md`), get the repository onto
   it, and restore `.env` from your password manager.
2. Start only the data stores:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait postgres minio qdrant
   ```
3. Put the private key in a file (for example `/tmp/identity.txt`), then restore,
   naming a backup (`list` shows them, newest last; nothing here is overwritten
   until you add `--yes-overwrite`):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile tools run --rm \
     -v /tmp/identity.txt:/identity.txt:ro backup restore ragconsumer-20261113T023000Z.tar.age --yes-overwrite
   shred -u /tmp/identity.txt
   ```
   If the file is not on the server the tool downloads it from the off-server
   bucket. It decrypts, checks every file against the backup's manifest, restores
   the three stores, and then compares row counts, document count and indexed
   fragments with what the backup recorded. Any mismatch stops with an error.
4. Start everything: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
   (This also recreates the storage service accounts and policies.)
5. Sign in, open a matter, and search for a phrase you know is in a document.

**On the existing server** (restoring over what is there): first stop the
services that use the data, `docker compose stop backend ingestion-worker mcp_server`,
then do step 3 and start them again. This replaces the current data with the
backup's, so it loses everything since that backup.

If the search index ever looks out of step with the documents (for example a
document was uploaded in the minutes between the database dump and the index
snapshot), rebuild it: `docker compose exec backend python scripts/reindex_all.py --yes`.

## Proving it works

`bash deploy/test-backup.sh` is the restore drill. It takes a backup of the
running stack, restores it into a second empty set of stores, and compares them
independently of the backup tool: row counts of every table, user accounts
including password hashes, every document's checksum, and every vector and text
in the search index. It also checks that a backup is unreadable without the key,
that a wrong key or a damaged file is refused *without changing anything*, that
the audit log is still append-only after a restore, and that a restore works
straight from the off-server bucket with no local file. It found and fixed one
real problem when first written (a wrong key showed a Python error instead of a
clear message).

**Run it after changing anything about backups, and do a real restore onto a
spare server at least every quarter**, since only that proves the private key,
the `.env` copy and your notes are all still good.

## Checking that last night's backup happened

```bash
journalctl -u ragconsumer-backup.service -n 30
docker compose --profile tools run --rm backup list
```

After each successful run the tool writes `last-success` in its volume; the
monitoring work (KAN-91) alerts when that is older than 26 hours.
