import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.auth import get_current_user, require_collection_role
from app.db import get_db
from app.errors import ApiError
from app.models import AiMatterSelection, CollectionMember, CollectionRole, User
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
        raise ApiError(
            status.HTTP_404_NOT_FOUND, "not_a_member", "That person is not a member of this collection"
        )
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
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "no_account_for_email",
            "No account with that email. Ask your firm's administrator to invite them first.",
        )
    existing = db.scalar(
        select(CollectionMember).where(
            CollectionMember.collection_id == collection_id,
            CollectionMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise ApiError(status.HTTP_409_CONFLICT, "already_member", "That person is already a member")

    member = CollectionMember(user_id=user.id, collection_id=collection_id, role=payload.role)
    db.add(member)
    audit.record(
        db, audit.MEMBER_ADDED, actor=current_user, collection_id=collection_id,
        target=user.email, detail={"role": payload.role.value},
    )
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
        raise ApiError(status.HTTP_409_CONFLICT, "last_owner", LAST_OWNER)

    previous_role = member.role
    member.role = payload.role
    target = db.get(User, user_id)
    audit.record(
        db, audit.MEMBER_ROLE_CHANGED, actor=current_user, collection_id=collection_id,
        target=target.email, detail={"role": payload.role.value, "previous_role": previous_role.value},
    )
    db.commit()
    return _out(member, target)


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
        raise ApiError(status.HTTP_409_CONFLICT, "last_owner", LAST_OWNER)

    removed = db.get(User, user_id)
    audit.record(
        db, audit.MEMBER_REMOVED, actor=current_user, collection_id=collection_id,
        target=removed.email if removed else None, detail={"role": member.role.value},
    )
    db.delete(member)
    # Tidy up their AI selection too. Not what protects the matter (the MCP
    # server re-checks membership on every call) but stale rows would
    # otherwise silently reactivate if they were ever re-added.
    selection = db.get(AiMatterSelection, (user_id, collection_id))
    if selection is not None:
        db.delete(selection)
    db.commit()
