import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `app` importable

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Case, CaseLawyer, User

SEED_USERS = [
    {"email": "alice@example.com", "password": "devpassword1"},
    {"email": "bob@example.com", "password": "devpassword2"},
]

SEED_CASES = ["Smith v. Jones", "Doe Estate", "Acme Corp Dispute"]

ACCESS = {
    "alice@example.com": ["Smith v. Jones", "Doe Estate"],
    "bob@example.com": ["Doe Estate", "Acme Corp Dispute"],
}


def get_or_create_user(db, email, password):
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user


def get_or_create_case(db, name):
    case = db.scalar(select(Case).where(Case.name == name))
    if case is not None:
        return case
    case = Case(name=name)
    db.add(case)
    db.flush()
    return case


def grant_access(db, user, case):
    link = db.scalar(
        select(CaseLawyer).where(
            CaseLawyer.user_id == user.id, CaseLawyer.case_id == case.id
        )
    )
    if link is None:
        db.add(CaseLawyer(user_id=user.id, case_id=case.id))


def main():
    db = SessionLocal()
    try:
        users = {
            u["email"]: get_or_create_user(db, u["email"], u["password"])
            for u in SEED_USERS
        }
        cases = {name: get_or_create_case(db, name) for name in SEED_CASES}

        for email, case_names in ACCESS.items():
            for case_name in case_names:
                grant_access(db, users[email], cases[case_name])

        db.commit()
    finally:
        db.close()

    print("Seeded users:")
    for u in SEED_USERS:
        print(f"  {u['email']} / {u['password']}")


if __name__ == "__main__":
    main()
