import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_collection_role
from app.db import get_db
from app.models import CollectionMember, CollectionRole, User
from app.schemas import MemberAdd, MemberOut, MemberRoleUpdate

router = APIRouter(prefix="/collections/{collection_id}/members", tags=["members"])

LAST_OWNER = "A collection must keep at least one owner."


def _out(member: CollectionMember, user: User) -> MemberOut:
    return MemberOut(user_id=user.id, email=user.email, role=member.role)


def _owner_count(db: Session, collection_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(CollectionMember)
        .where(
            CollectionMember.collection_id == collection_id,
            CollectionMember.role == CollectionRole.owner,
        )
    )


def _get_member(db: Session, collection_id: uuid.UUID, user_id: uuid.UUID) -> CollectionMember:
    member = db.scalar(
        select(CollectionMember).where(
            CollectionMember.collection_id == collection_id,
            CollectionMember.user_id == user_id,
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That person is not a member of this collection")
    return member


@router.get("", response_model=list[MemberOut])
def list_members(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Any member may see who else is on the matter; only owners may change it.
    require_collection_role(db, current_user.id, collection_id, CollectionRole.viewer)
    rows = db.execute(
        select(CollectionMember, User)
        .join(User, User.id == CollectionMember.user_id)
        .where(CollectionMember.collection_id == collection_id)
        .order_by(User.email)
    ).all()
    return [_out(m, u) for m, u in rows]


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    collection_id: uuid.UUID,
    payload: MemberAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_role(db, current_user.id, collection_id, CollectionRole.owner)

    # Only people who already have an account can be added; creating accounts
    # is the firm administrator's job (invitations), not a matter owner's.
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No account with that email. Ask your firm's administrator to invite them first.",
        )
    existing = db.scalar(
        select(CollectionMember).where(
            CollectionMember.collection_id == collection_id,
            CollectionMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That person is already a member")

    member = CollectionMember(user_id=user.id, collection_id=collection_id, role=payload.role)
    db.add(member)
    db.commit()
    return _out(member, user)


@router.patch("/{user_id}", response_model=MemberOut)
def change_member_role(
    collection_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_role(db, current_user.id, collection_id, CollectionRole.owner)
    member = _get_member(db, collection_id, user_id)

    demoting_an_owner = member.role == CollectionRole.owner and payload.role != CollectionRole.owner
    if demoting_an_owner and _owner_count(db, collection_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, LAST_OWNER)

    member.role = payload.role
    db.commit()
    return _out(member, db.get(User, user_id))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    collection_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Anyone may remove themselves (leave the matter); removing someone else
    # takes an owner.
    leaving = user_id == current_user.id
    require_collection_role(
        db,
        current_user.id,
        collection_id,
        CollectionRole.viewer if leaving else CollectionRole.owner,
    )
    member = _get_member(db, collection_id, user_id)

    if member.role == CollectionRole.owner and _owner_count(db, collection_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, LAST_OWNER)

    db.delete(member)
    db.commit()
