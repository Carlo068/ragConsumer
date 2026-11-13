"""Creates (or completes) the repo-root .env with strong random secrets.

    python scripts/generate_env.py

Never overwrites a value that already exists, so it is safe to rerun after
upgrades that add new variables. It warns about well-known weak values it finds
(postgres, minioadmin, ...), which it will not change for you: changing a
database password also means changing it inside the running database.
"""

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
    "MINIO_ROOT_USER": lambda: "minio-root",
    "MINIO_ROOT_PASSWORD": URLSAFE,
    "BACKEND_MINIO_ACCESS_KEY": lambda: "rag-backend",
    "BACKEND_MINIO_SECRET_KEY": URLSAFE,
    "WORKER_MINIO_ACCESS_KEY": lambda: "rag-worker",
    "WORKER_MINIO_SECRET_KEY": URLSAFE,
    "QDRANT_API_KEY": URLSAFE,
    "SESSION_SECRET": URLSAFE,
}

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
    existing_text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    existing = parse(existing_text)

    added = [name for name in VARIABLES if name not in existing]
    lines = []
    for name in added:
        lines.append(f"{name}={VARIABLES[name]()}")
    if lines:
        prefix = "" if not existing_text or existing_text.endswith("\n") else "\n"
        with ENV_PATH.open("a", encoding="utf-8", newline="\n") as f:
            f.write(prefix + "\n".join(lines) + "\n")

    print(f"{ENV_PATH}: added {len(added)} variable(s)" + (f": {', '.join(added)}" if added else ""))

    weak = [n for n in SECRET_NAMES if existing.get(n, "").lower() in WEAK]
    if weak:
        print(f"WARNING: weak default value(s) in use for {', '.join(weak)}. Replace them before production.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
