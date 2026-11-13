"""Keeps .env.example honest. Fails (exit 1) when:

  * a setting the stack reads is missing from .env.example (people would not
    know it exists),
  * .env.example lists a setting nothing reads any more,
  * a secret in .env.example has anything but the <random> placeholder, or any
    value looks like a real credential,
  * a variable docker compose REQUIRES is not produced by generate_env.py (so
    "generate, then start" would not work),
  * .env itself is tracked by git.

    python scripts/check_env_example.py
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

SECRET_SUFFIXES = ("PASSWORD", "SECRET_KEY", "API_KEY", "SECRET", "ACCESS_KEY", "TOKEN")
# Settings read straight from .env by scripts and the monitor, not through compose.
READ_BY_SCRIPTS = [ROOT / "deploy" / "monitor.sh", ROOT / "deploy" / "deploy.sh"]


def used_names() -> dict[str, str]:
    """name -> where it is read."""
    found: dict[str, str] = {}
    for path in sorted(ROOT.glob("docker-compose*.yml")):
        for name in re.findall(r"\$\{([A-Z][A-Z0-9_]*)", path.read_text(encoding="utf-8")):
            found.setdefault(name, path.name)
    caddy = ROOT / "deploy" / "Caddyfile"
    for name in re.findall(r"\{\$([A-Z][A-Z0-9_]*)", caddy.read_text(encoding="utf-8")):
        found.setdefault(name, "Caddyfile")
    for path in READ_BY_SCRIPTS:
        text = path.read_text(encoding="utf-8")
        for name in re.findall(r"env_value ([A-Z][A-Z0-9_]*)", text):
            found.setdefault(name, path.name)
        for name in re.findall(r"\$\{(MONITOR_[A-Z0-9_]+)", text):
            found.setdefault(name, path.name)
    return found


def example_entries() -> dict[str, tuple[str, bool]]:
    """name -> (value, is_commented_out)"""
    entries = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#\s*)?([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            entries[match.group(2)] = (match.group(3).strip(), bool(match.group(1)))
    return entries


def required_by_compose() -> set[str]:
    names = set()
    for path in ROOT.glob("docker-compose*.yml"):
        names.update(re.findall(r"\$\{([A-Z][A-Z0-9_]*):\?", path.read_text(encoding="utf-8")))
    return names


def main() -> int:
    problems: list[str] = []
    used = used_names()
    entries = example_entries()

    for name, where in sorted(used.items()):
        if name not in entries:
            problems.append(f"{name} is read by {where} but is missing from .env.example")
    for name in sorted(entries):
        if name not in used:
            problems.append(f"{name} is in .env.example but nothing reads it")

    for name, (value, commented) in sorted(entries.items()):
        is_secret = name.endswith(SECRET_SUFFIXES) and name not in {"BACKEND_MINIO_ACCESS_KEY", "WORKER_MINIO_ACCESS_KEY"}
        if is_secret and value not in ("", "<random>"):
            problems.append(f"{name} must be empty or <random> in .env.example, not a value")
        if not is_secret and re.fullmatch(r"[A-Za-z0-9_\-]{24,}", value or "") and not value.startswith("age1"):
            problems.append(f"{name} looks like a real credential in .env.example")
        if not commented and is_secret and value != "<random>":
            problems.append(f"{name} is set in .env.example; secrets there must be <random>")

    from generate_env import FROM_OPTIONS, VARIABLES

    for name in sorted(required_by_compose()):
        if name not in VARIABLES and name not in FROM_OPTIONS:
            problems.append(f"docker compose requires {name} but scripts/generate_env.py does not create it")
    for name in sorted(VARIABLES):
        if name not in entries or entries[name][1]:
            problems.append(f"generate_env.py creates {name} but .env.example does not list it as a required (uncommented) setting")

    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", ".env"], cwd=ROOT, capture_output=True, text=True)
    if tracked.returncode == 0:
        problems.append(".env is tracked by git: remove it from the repository and rotate every secret in it")

    if problems:
        print("ENV EXAMPLE PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print(f"OK: {len(entries)} settings listed in .env.example, all {len(used)} that the stack reads are covered, no real values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
