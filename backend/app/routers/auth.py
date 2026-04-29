# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.audit import log_event
from app.utils.auth import verify_password, create_token
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        log_event(
            db,
            actor=None,
            action="auth.login_failed",
            metadata={"email": body.email},
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        log_event(
            db,
            actor=user,
            action="auth.login_blocked",
            metadata={"reason": "account_inactive"},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_token(str(user.id), user.email, user.role.value)

    log_event(db, actor=user, action="auth.login")
    db.commit()

    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
