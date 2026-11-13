# Secrets on the server

Every password and key lives in **one file, `.env`, on the server**. It is never
committed to git (`.gitignore` excludes it, along with the `.env.bak-*` copies
the rotation script makes), never baked into an image, and never sent in chat or
email. The only file in git is `.env.example`, which has placeholders.

## Creating them

```bash
python scripts/generate_env.py        # writes .env with fresh random values
```

It never overwrites a value that already exists (it only adds missing ones) and
sets the file to mode 600. Run it on the server itself, so the values never
exist anywhere else.

## Who can read them

| Where | Rule |
|---|---|
| `.env` on the server | Owned by `deploy`, mode `600` (nobody else can read it). `deploy/check-hardening.sh` fails if this is not so. |
| Backups of `.env` | Keep them only in the encrypted off-server backup (KAN-89), never on a laptop or in a chat. |
| Containers | Each service receives only the values it needs through its `environment:` block in `docker-compose.yml`. The worker, for example, has read-only storage access and cannot touch the backend's account. |
| Logs | Before pasting a log anywhere to get help, search it for `SECRET`, `PASSWORD` and `KEY`. |

## What each secret protects

| Secret | Protects | Rotating it |
|---|---|---|
| `SESSION_SECRET` | Signs the login cookie. | Signs everyone out. |
| `POSTGRES_PASSWORD` | The database with accounts, matters, the audit log. | Brief restart of backend, worker and MCP server. |
| `MINIO_ROOT_PASSWORD` | Administration of document storage. Running services never use it; only the on-demand backup tool does. | MinIO restarts briefly. |
| `BACKEND_MINIO_SECRET_KEY` | The backend's storage account (read, write, delete documents). | Backend restarts. |
| `WORKER_MINIO_SECRET_KEY` | The worker's storage account (read-only). | Worker restarts. |
| `QDRANT_API_KEY` | Full access to the search index, and the key that signs the per-search tokens limiting each person to their own matters. **The most sensitive one.** | Qdrant and its clients restart. Indexed data is unaffected. |

## Rotating

One command per secret. It generates the new value, applies it where the secret
actually lives (for Postgres, inside the database first), saves it in `.env`,
recreates only the services that use it, and then checks that the stack really
works with the new value:

```bash
python scripts/rotate_secret.py QDRANT_API_KEY --dry-run     # shows the effect, changes nothing
python scripts/rotate_secret.py QDRANT_API_KEY
```

On the production server add the production compose file:

```bash
COMPOSE_FILES="docker-compose.yml docker-compose.prod.yml" python scripts/rotate_secret.py QDRANT_API_KEY
```

The previous `.env` is kept as `.env.bak-<time>` (mode 600) so you can go back
if the check fails; the script says exactly how. **Delete that file once you
have confirmed everything works**, because it contains the old secrets.

All six were rotated one after another on a running stack, and the full check
suite (including the live Qdrant isolation check) passed afterwards.

### When to rotate

- Immediately, if a secret may have been seen by someone who should not have:
  a screenshot, a pasted log, a laptop that was lost, a person with server access
  who has left.
- When anyone who had shell access to the server leaves the firm or the project.
- Otherwise every 6 months is a sensible routine; pick a quiet time, as
  `SESSION_SECRET` and the others interrupt people for about a minute.

### Not covered by the script

- **People's passwords** are not here: they are stored only as argon2 hashes in the
  database. Each person changes theirs under "Mi cuenta y contraseña", and an
  administrator can issue a reset link (`../account-security.md`).
- **Personal MCP access tokens** (`rag_…`) belong to each user, who can revoke and
  recreate them from the Connect page; an administrator can disable an account,
  which ends its sessions and revokes its keys at once (`../account-security.md`).
- **The SSH key** for `deploy` is replaced by editing
  `/home/deploy/.ssh/authorized_keys` (see `03-server-hardening.md`).
- **The provider account password and API tokens** are managed at the provider,
  with two-factor authentication on.
