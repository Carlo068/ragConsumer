import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `app` importable

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Collection, CollectionMember, User

SEED_USERS = [
    {"email": "alice@example.com", "password": "devpassword1"},
    {"email": "bob@example.com", "password": "devpassword2"},
]

SEED_COLLECTIONS = ["Smith v. Jones", "Doe Estate", "Acme Corp Dispute"]

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


def get_or_create_collection(db, name):
    collection = db.scalar(select(Collection).where(Collection.name == name))
    if collection is not None:
        return collection
    collection = Collection(name=name)
    db.add(collection)
    db.flush()
    return collection


def grant_access(db, user, collection):
    link = db.scalar(
        select(CollectionMember).where(
            CollectionMember.user_id == user.id,
            CollectionMember.collection_id == collection.id,
        )
    )
    if link is None:
        db.add(CollectionMember(user_id=user.id, collection_id=collection.id))


def main():
    db = SessionLocal()
    try:
        users = {
            u["email"]: get_or_create_user(db, u["email"], u["password"])
            for u in SEED_USERS
        }
        collections = {
            name: get_or_create_collection(db, name) for name in SEED_COLLECTIONS
        }

        for email, collection_names in ACCESS.items():
            for collection_name in collection_names:
                grant_access(db, users[email], collections[collection_name])

        db.commit()
    finally:
        db.close()

    print("Seeded users:")
    for u in SEED_USERS:
        print(f"  {u['email']} / {u['password']}")


if __name__ == "__main__":
    main()
