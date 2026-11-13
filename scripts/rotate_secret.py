"""Rotates one secret: generates a new value, saves it in .env, applies it
where the secret actually lives, restarts what depends on it, and checks the
stack still works.

    python scripts/rotate_secret.py QDRANT_API_KEY
    python scripts/rotate_secret.py POSTGRES_PASSWORD --dry-run

Secrets: SESSION_SECRET, POSTGRES_PASSWORD, BACKEND_DB_PASSWORD, MCP_DB_PASSWORD,
WORKER_DB_PASSWORD, MINIO_ROOT_PASSWORD, BACKEND_MINIO_SECRET_KEY,
WORKER_MINIO_SECRET_KEY, QDRANT_API_KEY.

In production add the compose files:
    COMPOSE_FILES="docker-compose.yml docker-compose.prod.yml" python scripts/rotate_secret.py ...

The previous .env is kept as .env.bak-<time> (readable only by you); delete it
once you have confirmed all is well. What each rotation does to people is
printed first (for example, rotating SESSION_SECRET signs everyone out).
"""

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
COMPOSE_FILES = os.environ.get("COMPOSE_FILES", "docker-compose.yml").split()

# What each secret touches. "recreate" lists the services to recreate so they
# read the new value (a restart alone does not re-read .env).
SECRETS = {
    "SESSION_SECRET": {
        "effect": "Everyone is signed out and has to sign in again (about a minute of interruption).",
        "recreate": ["backend"],
    },
    "POSTGRES_PASSWORD": {
        "effect": "The database owner's password is changed inside the database too. Only the one-shot migrate step uses it, so nothing running restarts.",
        "recreate": ["migrate"],
    },
    "BACKEND_DB_PASSWORD": {
        "effect": "The web API's database account gets a new password (set inside the database by the migrate step); the backend restarts (about a minute).",
        "recreate": ["migrate", "backend"],
    },
    "MCP_DB_PASSWORD": {
        "effect": "The AI connection's database account gets a new password; the MCP server restarts (about a minute).",
        "recreate": ["migrate", "mcp_server"],
    },
    "WORKER_DB_PASSWORD": {
        "effect": "The document worker's database account gets a new password; the worker restarts (about a minute).",
        "recreate": ["migrate", "ingestion-worker"],
    },
    "MINIO_ROOT_PASSWORD": {
        "effect": "Only the administration account changes; MinIO restarts briefly and the service accounts are re-applied.",
        "recreate": ["minio", "minio-init", "backend", "ingestion-worker"],
    },
    "BACKEND_MINIO_SECRET_KEY": {
        "effect": "The backend's storage account gets a new secret; the backend restarts.",
        "recreate": ["minio-init", "backend"],
    },
    "WORKER_MINIO_SECRET_KEY": {
        "effect": "The worker's storage account gets a new secret; the worker restarts.",
        "recreate": ["minio-init", "ingestion-worker"],
    },
    "QDRANT_API_KEY": {
        "effect": "Qdrant, which signs the per-search tokens, restarts with the new key together with everything that uses it (about a minute). Indexed data is unaffected.",
        "recreate": ["qdrant", "backend", "ingestion-worker", "mcp_server"],
    },
}


def compose(*args: str, capture: bool = False, check: bool = True, input_text: str | None = None):
    command = ["docker", "compose"]
    for f in COMPOSE_FILES:
        command += ["-f", f]
    command += list(args)
    return subprocess.run(command, cwd=ROOT, capture_output=capture, text=True, check=check, input=input_text)


def read_env() -> dict[str, str]:
    values = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
    return values


def write_env_value(name: str, value: str) -> Path:
    backup = ENV_PATH.with_name(f".env.bak-{time.strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(ENV_PATH, backup)
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.partition("=")[0].strip() == name:
            lines[i] = f"{name}={value}"
            replaced = True
    if not replaced:
        lines.append(f"{name}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for path in (ENV_PATH, backup):
        try:
            path.chmod(0o600)
        except OSError:
            pass  # not meaningful on Windows
    return backup


def python_in(service: str, code: str) -> bool:
    if service == "migrate":  # a one-shot service: run a throwaway copy of it
        result = compose("run", "--rm", "--no-deps", "-T", "--entrypoint", "python", service, "-c", code, capture=True, check=False)
    else:
        result = compose("exec", "-T", service, "python", "-c", code, capture=True, check=False)
    return result.returncode == 0


CONNECT = "import os; from sqlalchemy import create_engine, text; create_engine(os.environ['DATABASE_URL']).connect().execute(text('select 1'))"


# A real use of the rotated secret, from inside the stack.
CHECKS = {
    "SESSION_SECRET": ("backend", "import app.main"),
    "POSTGRES_PASSWORD": ("migrate", CONNECT),  # connects as the owner
    "BACKEND_DB_PASSWORD": ("backend", CONNECT),
    "MCP_DB_PASSWORD": ("mcp_server", CONNECT),
    "WORKER_DB_PASSWORD": ("ingestion-worker", CONNECT),
    "MINIO_ROOT_PASSWORD": (
        "backend",
        "from app.storage import minio_client, BUCKET_NAME; assert minio_client.bucket_exists(BUCKET_NAME)",
    ),
    "BACKEND_MINIO_SECRET_KEY": (
        "backend",
        "from app.storage import minio_client, BUCKET_NAME; assert minio_client.bucket_exists(BUCKET_NAME)",
    ),
    "WORKER_MINIO_SECRET_KEY": (
        "ingestion-worker",
        "import os; from minio import Minio; c = Minio(os.environ['MINIO_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=False); c._get_region(os.environ['MINIO_BUCKET'])",
    ),
    "QDRANT_API_KEY": (
        "backend",
        "from app.vectorstore import qdrant_client; qdrant_client.get_collections()",
    ),
}


def verify(name: str, retries: int = 30) -> bool:
    service, code = CHECKS[name]
    for _ in range(retries):
        if python_in(service, code):
            return True
        time.sleep(2)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", choices=sorted(SECRETS))
    parser.add_argument("--dry-run", action="store_true", help="show what would happen and change nothing")
    args = parser.parse_args()
    spec = SECRETS[args.name]

    if not ENV_PATH.exists():
        print("No .env found. Run: python scripts/generate_env.py")
        return 2

    print(f"Rotating {args.name}")
    print(f"  Effect: {spec['effect']}")
    print(f"  Services recreated: {', '.join(spec['recreate'])}")
    if args.dry_run:
        print("Dry run: nothing changed.")
        return 0

    env = read_env()
    old = env.get(args.name, "")
    new = secrets.token_urlsafe(32)

    if args.name == "POSTGRES_PASSWORD":
        # Change it inside the database first, while the old connection still works.
        user = env.get("POSTGRES_USER", "postgres")
        db = env.get("POSTGRES_DB", "ragconsumer")
        sql = f"ALTER USER \"{user}\" PASSWORD '{new}'"
        compose("exec", "-T", "postgres", "psql", "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql, capture=True)
        print("  Changed the password inside Postgres.")

    backup = write_env_value(args.name, new)
    print(f"  Saved the new value in .env (previous file kept as {backup.name}).")

    compose("up", "-d", "--force-recreate", *spec["recreate"], capture=True)
    print("  Restarted the dependent services.")

    if verify(args.name):
        print(f"OK: {args.name} rotated and the stack is working with the new value.")
        print(f"Delete {backup.name} once you have confirmed everything is fine.")
        return 0

    print(f"PROBLEM: the stack did not come back healthy after rotating {args.name}.")
    print(f"To go back: copy {backup.name} over .env" + (
        ", and set the database password back (ALTER USER) if you rotated POSTGRES_PASSWORD." if args.name == "POSTGRES_PASSWORD" else "."
    ))
    if old:
        print("(The previous value is in that backup file.)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
