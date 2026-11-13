"""Create the firm's first administrator, or promote an existing user.

Accounts are invite-only, and only an admin can invite, so the very first
admin has to be created here:

    docker compose exec -it backend python scripts/create_admin.py --email ana@firm.mx

The password is prompted for (never passed on the command line, where it
would land in shell history). If the user already exists, they're promoted
to admin and their password is left unchanged.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `app` importable

from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--email", required=True)
    email = parser.parse_args().email.lower()

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            user.is_admin = True
            db.commit()
            print(f"{email} already existed and is now an administrator.")
            return 0

        password = getpass.getpass("Password: ")
        if len(password) < settings.MIN_PASSWORD_LENGTH:
            print(f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters.")
            return 1
        if getpass.getpass("Repeat password: ") != password:
            print("Passwords don't match.")
            return 1

        db.add(User(email=email, password_hash=hash_password(password), is_admin=True))
        db.commit()
        print(f"Created administrator {email}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
