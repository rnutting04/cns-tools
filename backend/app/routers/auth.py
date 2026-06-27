from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.audit import log_event
from app.utils.auth import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    generate_refresh_token,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_NAME = "refresh_token"
_COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/api/auth")


def _revoke_chain(db: Session, token: RefreshToken) -> None:
    """Walk the replaced_by chain and revoke every descendant."""
    current = token
    now = datetime.utcnow()
    while current:
        if current.revoked_at is None:
            current.revoked_at = now
        if current.replaced_by is None:
            break
        current = db.query(RefreshToken).filter(RefreshToken.id == current.replaced_by).first()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        log_event(db, actor=None, action="auth.login_failed", metadata={"email": body.email})
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        log_event(db, actor=user, action="auth.login_blocked", metadata={"reason": "account_inactive"})
        db.commit()
        raise HTTPException(status_code=403, detail="Account is inactive")

    raw_rt, rt_hash = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=rt_hash,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    ))

    access_token = create_access_token(str(user.id), user.email, user.role.value)
    log_event(db, actor=user, action="auth.login")
    db.commit()

    _set_refresh_cookie(response, raw_rt)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    record = db.query(RefreshToken).filter(
        RefreshToken.token_hash == hash_token(refresh_token)
    ).first()

    if not record:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Reuse of an already-rotated token is a strong signal of theft.
    if record.revoked_at is not None:
        log_event(
            db,
            actor=None,
            action="auth.refresh_token_reuse",
            metadata={"user_id": str(record.user_id)},
        )
        _revoke_chain(db, record)
        db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh token already used")

    if record.expires_at < datetime.utcnow():
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user or not user.is_active:
        record.revoked_at = datetime.utcnow()
        db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Rotate: revoke old, issue new, link chain
    raw_rt, rt_hash = generate_refresh_token()
    new_record = RefreshToken(
        user_id=user.id,
        token_hash=rt_hash,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=record.user_agent,
        ip_address=record.ip_address,
    )
    db.add(new_record)
    db.flush()  # populate new_record.id before linking

    record.revoked_at = datetime.utcnow()
    record.replaced_by = new_record.id

    access_token = create_access_token(str(user.id), user.email, user.role.value)
    db.commit()

    _set_refresh_cookie(response, raw_rt)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    if refresh_token:
        record = db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_token(refresh_token)
        ).first()
        if record and record.revoked_at is None:
            record.revoked_at = datetime.utcnow()
            db.commit()
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
