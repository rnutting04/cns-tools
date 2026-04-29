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
from app.services.audit import log_event
from app.utils.auth import hash_password, verify_password
from app.dependencies import get_current_user, require_admin, require_super_admin

# Resolve forward reference: UserWithAssociations.associations -> AssociationResponse
UserWithAssociations.model_rebuild(_types_namespace={"AssociationResponse": AssociationResponse})

router = APIRouter(prefix="/users", tags=["users"])


class RoleUpdate(BaseModel):
    role: UserRole


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


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
    current_user: User = Depends(require_admin),
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
    db.flush()
    log_event(
        db,
        actor=current_user,
        action="user.created",
        target_type="user",
        target_id=str(user.id),
        metadata={"email": user.email, "role": user.role.value, "title": user.title},
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updates = body.model_dump(exclude_unset=True)
    updates.pop("role", None)  # role changes go through /role endpoint
    for field, value in updates.items():
        setattr(user, field, value)
    log_event(
        db,
        actor=current_user,
        action="user.updated",
        target_type="user",
        target_id=str(user_id),
        metadata=updates,
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    old_role = user.role.value
    user.role = body.role
    log_event(
        db,
        actor=current_user,
        action="user.role_changed",
        target_type="user",
        target_id=str(user_id),
        metadata={"from": old_role, "to": body.role.value, "email": user.email},
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    log_event(
        db,
        actor=current_user,
        action="user.deactivated",
        target_type="user",
        target_id=str(user_id),
        metadata={"email": user.email},
    )
    db.commit()


@router.post("/me/change-password", status_code=204)
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(body.new_password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")

    if verify_password(body.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="New password must be different from current")

    was_required = current_user.password_change_required
    current_user.password_hash = hash_password(body.new_password)
    current_user.password_change_required = False
    log_event(
        db,
        actor=current_user,
        action="user.password_changed",
        target_type="user",
        target_id=str(current_user.id),
        metadata={"was_required": was_required},
    )
    db.commit()
