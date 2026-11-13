"""Creates (or completes) the repo-root .env with strong random secrets.

    python scripts/generate_env.py
    python scripts/generate_env.py --domain matters.yourfirm.mx    (production: also sets DOMAIN)

Never overwrites a value that already exists, so it is safe to rerun after
upgrades that add new variables. It warns about well-known weak values it finds
(postgres, minioadmin, ...), which it will not change for you: changing a
database password also means changing it inside the running database.
"""

import argparse
import re
import secrets
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# name -> value generator. Non-secret names are fixed; secrets are random.
URLSAFE = lambda: secrets.token_urlsafe(32)  # noqa: E731
VARIABLES = {
    "POSTGRES_USER": lambda: "ragapp",
    "POSTGRES_DB": lambda: "ragconsumer",
    "POSTGRES_PASSWORD": URLSAFE,
    "BACKEND_DB_PASSWORD": URLSAFE,
    "MCP_DB_PASSWORD": URLSAFE,
    "WORKER_DB_PASSWORD": URLSAFE,
    "MINIO_ROOT_USER": lambda: "minio-root",
    "MINIO_ROOT_PASSWORD": URLSAFE,
    "BACKEND_MINIO_ACCESS_KEY": lambda: "rag-backend",
    "BACKEND_MINIO_SECRET_KEY": URLSAFE,
    "WORKER_MINIO_ACCESS_KEY": lambda: "rag-worker",
    "WORKER_MINIO_SECRET_KEY": URLSAFE,
    "QDRANT_API_KEY": URLSAFE,
    "SESSION_SECRET": URLSAFE,
}

# Settings that are not generated but come from an option (production address).
FROM_OPTIONS = {"DOMAIN": "--domain"}

WEAK = {"postgres", "minioadmin", "password", "changeme", "dev-only-qdrant-key-replace-before-production"}
SECRET_NAMES = {n for n in VARIABLES if n.endswith(("PASSWORD", "SECRET_KEY", "API_KEY", "SECRET"))}


def parse(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or complete .env with strong random secrets.")
    parser.add_argument("--domain", help="public address for production, e.g. matters.yourfirm.mx (sets DOMAIN)")
    args = parser.parse_args()
    if args.domain and not re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?", args.domain):
        print(f"ERROR: '{args.domain}' is not a valid domain name (no https://, no path)")
        return 2

    existing_text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    existing = parse(existing_text)

    added = [name for name in VARIABLES if name not in existing]
    lines = []
    for name in added:
        lines.append(f"{name}={VARIABLES[name]()}")
    if args.domain and "DOMAIN" not in existing:
        added.append("DOMAIN")
        lines.append(f"DOMAIN={args.domain}")
    elif args.domain and existing.get("DOMAIN") != args.domain:
        print(f"NOTE: DOMAIN is already {existing.get('DOMAIN')} in .env and was left as it is.")
    if lines:
        prefix = "" if not existing_text or existing_text.endswith("\n") else "\n"
        with ENV_PATH.open("a", encoding="utf-8", newline="\n") as f:
            f.write(prefix + "\n".join(lines) + "\n")

    if ENV_PATH.exists():
        try:
            ENV_PATH.chmod(0o600)  # secrets: readable by the owner only (no effect on Windows)
        except OSError:
            pass

    print(f"{ENV_PATH}: added {len(added)} variable(s)" + (f": {', '.join(added)}" if added else ""))

    weak = [n for n in SECRET_NAMES if existing.get(n, "").lower() in WEAK]
    if weak:
        print(f"WARNING: weak default value(s) in use for {', '.join(weak)}. Replace them before production.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
