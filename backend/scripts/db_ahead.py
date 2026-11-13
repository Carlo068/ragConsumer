"""Tells the start-up script whether a failed `alembic upgrade head` is only
because the database is NEWER than this code.

That happens after a rollback: a newer release already migrated the database,
then the older code was put back. Migrations are written to be additive (see
docs/deployment/06-deploy-and-rollback.md), so the older code runs fine on the
newer schema and should be allowed to start. Any other failure (a migration that
errors, a database that cannot be reached) must still stop the start.

Exit status 0: the database is at a revision this code does not know.
Exit status 1: anything else.
"""

import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]


def database_is_ahead(engine: Engine, alembic_ini: Path = ROOT / "alembic.ini") -> bool:
    script = ScriptDirectory.from_config(Config(str(alembic_ini)))
    try:
        with engine.connect() as connection:
            revisions = [row[0] for row in connection.execute(text("select version_num from alembic_version"))]
    except Exception:
        return False  # no version table or no database: not "ahead", a real problem
    if not revisions:
        return False
    for revision in revisions:
        try:
            if script.get_revision(revision) is None:
                return True
        except Exception:
            return True
    return False


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    from app.db import engine

    ahead = database_is_ahead(engine)
    if ahead:
        print("The database is newer than this version (a later release migrated it). Starting anyway: migrations are additive.")
    sys.exit(0 if ahead else 1)
