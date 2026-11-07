# app/routers/users.py
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_super_admin
from app.models.association import UserAssociation
from app.models.user import User, UserRole
from app.schemas.association import AssociationResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate, UserWithAssociations
from app.services.audit import log_event
from app.services.email.tasks import password_changed_email, reset_password_email, welcome_email
from app.utils.auth import hash_password, verify_password

# Resolve forward reference: UserWithAssociations.associations -> AssociationResponse
UserWithAssociations.model_rebuild(_types_namespace={"AssociationResponse": AssociationResponse})

router = APIRouter(prefix="/users", tags=["users"])


class RoleUpdate(BaseModel):
    role: UserRole


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SendWelcomeRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=200)


class SendWelcomeResult(BaseModel):
    sent: int
    skipped: list[str] = []


def _issue_temp_password(user: User) -> str:
    """Replace a user's password with a fresh single-use one.

    Caller is responsible for logging the audit event, committing, and sending
    the mail that carries the returned password. The password is only ever held
    in memory and emailed — never stored in plaintext or written to the audit log.
    """
    temp_password = secrets.token_urlsafe(12)
    user.password_hash = hash_password(temp_password)
    user.password_change_required = True
    return temp_password


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

    temp_password = secrets.token_urlsafe(12)
    user = User(
        fname=body.fname,
        lname=body.lname,
        email=body.email,
        title=body.title,
        role=body.role,
        password_hash=hash_password(temp_password),
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

    welcome_email(user.email, user.fname, temp_password)

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
    if user_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot deactivate your own account")
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

    password_changed_email(current_user.email, current_user.fname)


@router.delete("/{user_id}/permanent", status_code=204)
def permanently_delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot delete your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_active:
        raise HTTPException(
            status_code=400, detail="User must be deactivated before being permanently deleted."
        )
    log_event(
        db,
        actor=current_user,
        action="user.permanently_deleted",
        target_type="user",
        target_id=str(user.id),
        metadata={"email": user.email, "role": user.role.value},
    )
    try:
        db.delete(user)
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="User has associated jobs or data and cannot be deleted. Deactivate them instead.",
        ) from err


@router.post("/{user_id}/reset-password", status_code=204)
def reset_user_password(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = _issue_temp_password(user)
    log_event(
        db,
        actor=current_user,
        action="user.password_reset",
        target_type="user",
        target_id=str(user_id),
        metadata={"email": user.email},
    )
    db.commit()

    reset_password_email(user.email, user.fname, temp_password)


# ─── Account access (welcome) ────────────────────────────────────────────────
#
# Accounts are provisioned by an admin before the user has ever signed in, so
# for a rollout to existing accounts there is nobody to "reset" a password for —
# the user has simply never received theirs. These two endpoints do mechanically
# the same thing as reset-password (issue a fresh single-use password) but send
# the welcome email instead, which reads as an invitation rather than a security
# alert. Kept separate from reset-password so the audit trail distinguishes
# "onboarded this person" from "an admin reset this person's password".


@router.post("/{user_id}/send-welcome", status_code=204)
def send_welcome_to_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="User is deactivated. Reactivate them before sending account access.",
        )

    temp_password = _issue_temp_password(user)
    log_event(
        db,
        actor=current_user,
        action="user.welcome_sent",
        target_type="user",
        target_id=str(user.id),
        metadata={"email": user.email},
    )
    db.commit()

    welcome_email(user.email, user.fname, temp_password)


@router.post("/send-welcome", response_model=SendWelcomeResult)
def send_welcome_bulk(
    body: SendWelcomeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Issue account access to several existing users at once.

    Deactivated and unknown users are skipped rather than failing the batch, so
    one stale selection can't block a rollout to everyone else. All password
    changes commit as a single transaction; the emails are queued afterwards so
    a mail failure can't leave a user holding a password that was rolled back.
    """
    users = db.query(User).filter(User.id.in_(body.user_ids)).all()
    by_id = {u.id: u for u in users}

    issued: list[tuple[User, str]] = []
    skipped: list[str] = []

    for user_id in body.user_ids:
        user = by_id.get(user_id)
        if user is None:
            skipped.append(f"{user_id} (not found)")
            continue
        if not user.is_active:
            skipped.append(f"{user.email} (deactivated)")
            continue
        issued.append((user, _issue_temp_password(user)))

    if issued:
        log_event(
            db,
            actor=current_user,
            action="user.welcome_sent_bulk",
            target_type="user",
            metadata={
                "count": len(issued),
                "emails": [u.email for u, _ in issued],
                "skipped": skipped,
            },
        )
    db.commit()

    for user, temp_password in issued:
        welcome_email(user.email, user.fname, temp_password)

    return SendWelcomeResult(sent=len(issued), skipped=skipped)
