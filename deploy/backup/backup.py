#!/usr/bin/env python3
"""Encrypted backup and restore of everything that matters: the Postgres
database, the stored documents (MinIO) and the search index (Qdrant).

    backup          take a backup, encrypt it, copy it off the server, apply retention
    restore FILE    put a backup back (needs the private key; see docs/deployment/05-backups.md)
    list            show the backups that exist, here and off the server
    prune           apply the retention policy now

Run through Docker Compose (see docs): the tool runs in a throwaway container
on the stack's network, so it needs nothing installed on the server.

Backups are encrypted with `age` to a PUBLIC key held on the server. The
private key is kept elsewhere, so someone who gets into the server (or the
backup storage) cannot read old backups.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from retention import NAME_RE, select_delete

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/backups"))
BUCKET = os.environ.get("MINIO_BUCKET", "documents")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
LOCAL_KEEP = int(os.environ.get("BACKUP_LOCAL_KEEP", "7"))
POLICY = dict(
    daily=int(os.environ.get("BACKUP_KEEP_DAILY", "14")),
    weekly=int(os.environ.get("BACKUP_KEEP_WEEKLY", "8")),
    monthly=int(os.environ.get("BACKUP_KEEP_MONTHLY", "12")),
)


class BackupError(Exception):
    pass


def log(message: str) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}] {message}", flush=True)


def run(command: list[str], *, env_extra: dict | None = None, capture: bool = False, **kwargs):
    env = {**os.environ, **(env_extra or {})}
    result = subprocess.run(command, env=env, capture_output=capture, text=True, **kwargs)
    if result.returncode != 0:
        detail = (result.stderr or "").strip()[-400:] if capture else ""
        raise BackupError(f"{command[0]} failed (exit {result.returncode}) {detail}".strip())
    return result


# --- configuration of the storage systems -----------------------------------

def minio_env() -> dict:
    return {
        "RCLONE_CONFIG_MINIO_TYPE": "s3",
        "RCLONE_CONFIG_MINIO_PROVIDER": "Minio",
        "RCLONE_CONFIG_MINIO_ENDPOINT": "http://" + os.environ.get("MINIO_ENDPOINT", "minio:9000"),
        "RCLONE_CONFIG_MINIO_ACCESS_KEY_ID": os.environ["MINIO_ROOT_USER"],
        "RCLONE_CONFIG_MINIO_SECRET_ACCESS_KEY": os.environ["MINIO_ROOT_PASSWORD"],
    }


def offsite_remote() -> tuple[str, dict] | None:
    """The off-server destination: any S3-compatible bucket (Backblaze B2,
    Wasabi, Hetzner, AWS, Cloudflare R2, DigitalOcean...)."""
    bucket = os.environ.get("BACKUP_S3_BUCKET", "").strip()
    if not bucket:
        return None
    env = {
        "RCLONE_CONFIG_OFFSITE_TYPE": "s3",
        "RCLONE_CONFIG_OFFSITE_PROVIDER": os.environ.get("BACKUP_S3_PROVIDER", "Other"),
        "RCLONE_CONFIG_OFFSITE_ENDPOINT": os.environ.get("BACKUP_S3_ENDPOINT", ""),
        "RCLONE_CONFIG_OFFSITE_REGION": os.environ.get("BACKUP_S3_REGION", ""),
        "RCLONE_CONFIG_OFFSITE_ACCESS_KEY_ID": os.environ.get("BACKUP_S3_ACCESS_KEY", ""),
        "RCLONE_CONFIG_OFFSITE_SECRET_ACCESS_KEY": os.environ.get("BACKUP_S3_SECRET_KEY", ""),
        "RCLONE_CONFIG_OFFSITE_NO_CHECK_BUCKET": "true",
    }
    prefix = os.environ.get("BACKUP_S3_PREFIX", "ragconsumer").strip("/")
    return f"offsite:{bucket}/{prefix}", env


# --- Postgres ----------------------------------------------------------------

def psql(sql: str) -> str:
    return run(["psql", "-At", "-v", "ON_ERROR_STOP=1", "-c", sql], capture=True).stdout.strip()


def postgres_counts() -> dict[str, int]:
    tables = psql("select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1").splitlines()
    return {t: int(psql(f'select count(*) from public."{t}"')) for t in tables}


# --- Qdrant ------------------------------------------------------------------

def qdrant(method: str, path: str, *extra: str) -> dict:
    command = ["curl", "-sS", "-f", "-X", method, "-H", f"api-key: {os.environ['QDRANT_API_KEY']}", *extra, QDRANT_URL + path]
    return json.loads(run(command, capture=True).stdout or "{}")


def qdrant_collections() -> list[str]:
    return sorted(c["name"] for c in qdrant("GET", "/collections")["result"]["collections"])


def qdrant_points(name: str) -> int:
    return qdrant("GET", f"/collections/{name}")["result"]["points_count"]


# --- files -------------------------------------------------------------------

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checksums(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root).as_posix()): sha256(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name != "MANIFEST.json"}


def local_backups() -> list[str]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.name for p in BACKUP_DIR.iterdir() if NAME_RE.match(p.name))


def remote_backups() -> list[str] | None:
    remote = offsite_remote()
    if not remote:
        return None
    path, env = remote
    out = run(["rclone", "lsf", path], env_extra=env, capture=True).stdout
    return sorted(line.strip() for line in out.splitlines() if NAME_RE.match(line.strip()))


# --- backup ------------------------------------------------------------------

def cmd_backup(args) -> int:
    recipient = os.environ.get("BACKUP_AGE_RECIPIENT", "").strip()
    if not recipient.startswith("age1"):
        raise BackupError("BACKUP_AGE_RECIPIENT is not set (the public key, starting age1...). See docs/deployment/05-backups.md.")
    remote = offsite_remote()
    if not remote and os.environ.get("BACKUP_ALLOW_LOCAL_ONLY", "").lower() != "true":
        raise BackupError("No off-server destination: set BACKUP_S3_BUCKET (and its keys). A backup that lives only on this server is lost with it.")

    started = dt.datetime.now(dt.timezone.utc)
    name = f"ragconsumer-{started:%Y%m%dT%H%M%SZ}.tar.age"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="backup-") as tmp:
        work = Path(tmp)

        log("Database: dumping Postgres")
        run(["pg_dump", "-Fc", "--no-owner", "-f", str(work / "postgres.dump")])
        counts = postgres_counts()

        log("Documents: copying the stored files")
        (work / "documents").mkdir()
        run(["rclone", "copy", f"minio:{BUCKET}", str(work / "documents"), "--transfers", "4"], env_extra=minio_env())

        log("Search index: taking Qdrant snapshots")
        (work / "qdrant").mkdir()
        points = {}
        for collection in qdrant_collections():
            points[collection] = qdrant_points(collection)
            snap = qdrant("POST", f"/collections/{collection}/snapshots?wait=true")["result"]["name"]
            run(["curl", "-sS", "-f", "-H", f"api-key: {os.environ['QDRANT_API_KEY']}", "-o", str(work / "qdrant" / f"{collection}.snapshot"),
                 f"{QDRANT_URL}/collections/{collection}/snapshots/{snap}"])
            qdrant("DELETE", f"/collections/{collection}/snapshots/{snap}?wait=true")

        manifest = {
            "format": 1,
            "created_at": started.isoformat(),
            "postgres_rows": counts,
            "document_objects": sum(1 for p in (work / "documents").rglob("*") if p.is_file()),
            "qdrant_points": points,
            "files": checksums(work),
        }
        (work / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        log("Encrypting")
        partial = BACKUP_DIR / (name + ".partial")
        age = subprocess.Popen(["age", "-r", recipient, "-o", str(partial)], stdin=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=age.stdin, mode="w|") as tar:
                tar.add(work, arcname=".")
        finally:
            age.stdin.close()
        if age.wait() != 0:
            partial.unlink(missing_ok=True)
            raise BackupError("encryption failed")
        partial.rename(BACKUP_DIR / name)

    size = (BACKUP_DIR / name).stat().st_size
    log(f"Backup written: {name} ({size / 1024 / 1024:.1f} MB), {manifest['document_objects']} documents, {sum(points.values())} indexed chunks")

    if remote:
        path, env = remote
        log("Copying off the server")
        run(["rclone", "copyto", str(BACKUP_DIR / name), f"{path}/{name}"], env_extra=env)
        run(["rclone", "check", "--one-way", str(BACKUP_DIR), path, "--include", name], env_extra=env)
        log("Off-server copy verified")

    prune(now=started)
    (BACKUP_DIR / "last-success").write_text(started.isoformat() + "\n" + name + "\n", encoding="utf-8")
    log("Backup finished OK")
    return 0


# --- retention ---------------------------------------------------------------

def prune(now: dt.datetime | None = None) -> None:
    now = now or dt.datetime.now(dt.timezone.utc)
    names = local_backups()
    for name in names[:-LOCAL_KEEP] if LOCAL_KEEP > 0 else []:
        (BACKUP_DIR / name).unlink()
        log(f"Removed old local backup {name}")

    remote = offsite_remote()
    if remote and os.environ.get("BACKUP_PRUNE_REMOTE", "true").lower() == "true":
        path, env = remote
        for name in select_delete(remote_backups() or [], now, **POLICY):
            run(["rclone", "deletefile", f"{path}/{name}"], env_extra=env)
            log(f"Removed old off-server backup {name} (retention policy)")


def cmd_prune(args) -> int:
    prune()
    return 0


def cmd_list(args) -> int:
    print("On this server:")
    for name in local_backups():
        print("  ", name)
    remote = remote_backups()
    print("Off the server:" if remote is not None else "Off the server: not configured")
    for name in remote or []:
        print("  ", name)
    return 0


# --- restore -----------------------------------------------------------------

def cmd_restore(args) -> int:
    identity = Path(args.identity)
    if not identity.is_file():
        raise BackupError(f"private key file not found at {identity}: mount it into the container (see docs)")
    if not args.yes_overwrite:
        raise BackupError("restore OVERWRITES the database, the documents and the search index of this stack. Re-run with --yes-overwrite once you are sure this is the stack you mean to replace.")

    source = Path(args.file)
    if not source.is_file():
        source = BACKUP_DIR / args.file
    if not source.is_file():
        remote = offsite_remote()
        if not remote:
            raise BackupError(f"{args.file} not found here and no off-server storage is configured")
        path, env = remote
        log("Downloading from the off-server storage")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        source = BACKUP_DIR / Path(args.file).name
        run(["rclone", "copyto", f"{path}/{Path(args.file).name}", str(source)], env_extra=env)

    with tempfile.TemporaryDirectory(prefix="restore-") as tmp:
        work = Path(tmp)
        log("Decrypting")
        age = subprocess.Popen(["age", "-d", "-i", str(identity), str(source)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            with tarfile.open(fileobj=age.stdout, mode="r|") as tar:
                tar.extractall(work, filter="data")
        except (tarfile.TarError, EOFError):
            age.kill()
            age.wait()
            raise BackupError("could not decrypt: wrong private key, or the file is damaged. Nothing was changed.") from None
        if age.wait() != 0:
            raise BackupError("could not decrypt: wrong private key, or the file is damaged. Nothing was changed.")

        manifest = json.loads((work / "MANIFEST.json").read_text(encoding="utf-8"))
        log("Checking the contents against the manifest")
        actual = checksums(work)
        if actual != manifest["files"]:
            bad = sorted(set(actual) ^ set(manifest["files"]) | {k for k in actual if k in manifest["files"] and actual[k] != manifest["files"][k]})
            raise BackupError(f"backup is damaged or incomplete ({len(bad)} file(s) differ, e.g. {bad[:3]}); nothing was changed")

        log("Database: restoring Postgres")
        run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--exit-on-error", "-d", os.environ["PGDATABASE"], str(work / "postgres.dump")])

        log("Documents: restoring the stored files")
        env = minio_env()
        run(["rclone", "mkdir", f"minio:{BUCKET}"], env_extra=env)
        run(["rclone", "copy", str(work / "documents"), f"minio:{BUCKET}", "--transfers", "4"], env_extra=env)

        log("Search index: restoring Qdrant")
        for snapshot in sorted((work / "qdrant").glob("*.snapshot")):
            qdrant("POST", f"/collections/{snapshot.stem}/snapshots/upload?priority=snapshot&wait=true", "-F", f"snapshot=@{snapshot}")

    log("Checking what was restored")
    problems = []
    now_rows = postgres_counts()
    for table, rows in manifest["postgres_rows"].items():
        if now_rows.get(table) != rows:
            problems.append(f"table {table}: {now_rows.get(table)} rows, backup had {rows}")
    for collection, count in manifest["qdrant_points"].items():
        if qdrant_points(collection) != count:
            problems.append(f"collection {collection}: {qdrant_points(collection)} chunks, backup had {count}")
    listed = run(["rclone", "lsf", "-R", "--files-only", f"minio:{BUCKET}"], env_extra=minio_env(), capture=True).stdout.split()
    if len(listed) < manifest["document_objects"]:
        problems.append(f"documents: {len(listed)} files, backup had {manifest['document_objects']}")
    if problems:
        raise BackupError("restore finished but does not match the backup:\n  " + "\n  ".join(problems))
    log(f"Restore OK: backup of {manifest['created_at']}, {manifest['document_objects']} documents, {sum(manifest['qdrant_points'].values())} indexed chunks")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("backup").set_defaults(func=cmd_backup)
    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("prune").set_defaults(func=cmd_prune)
    restore = sub.add_parser("restore")
    restore.add_argument("file", help="backup file name (local or off-server)")
    restore.add_argument("--identity", default="/identity.txt", help="path of the private key inside the container")
    restore.add_argument("--yes-overwrite", action="store_true")
    restore.set_defaults(func=cmd_restore)
    args = parser.parse_args()
    try:
        return args.func(args)
    except BackupError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
