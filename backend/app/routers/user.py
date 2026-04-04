# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.database import get_db
from app.models.user import User, UserRole
from app.models.association import UserAssociation
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserWithAssociations
from app.schemas.association import AssociationResponse
from app.utils.auth import hash_password
from app.dependencies import require_admin, require_super_admin

# Resolve forward reference: UserWithAssociations.associations -> AssociationResponse
UserWithAssociations.model_rebuild(_types_namespace={"AssociationResponse": AssociationResponse})

router = APIRouter(prefix="/users", tags=["users"])


class RoleUpdate(BaseModel):
    role: UserRole


def _serialize_user_with_associations(user: User) -> dict:
    data = UserResponse.model_validate(user).model_dump()
    data["associations"] = [
        AssociationResponse.model_validate(ua.association).model_dump()
        for ua in user.associations
        if ua.association is not None
    ]
    return data


@router.get("", response_model=list[UserWithAssociations])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = (
        db.query(User)
        .options(joinedload(User.associations).joinedload(UserAssociation.association))
        .all()
    )
    return [_serialize_user_with_associations(u) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already in use")
    user = User(
        fname=body.fname,
        lname=body.lname,
        email=body.email,
        title=body.title,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updates = body.model_dump(exclude_unset=True)
    updates.pop("role", None)  # role changes go through /role endpoint
    for field, value in updates.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
