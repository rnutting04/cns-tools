from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.association import UserAssociation
from app.schemas.user import UserResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/managers", tags=["managers"])


@router.get("", response_model=list[UserResponse])
def list_managers(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return only users who are assigned as a manager of at least one association."""
    return (
        db.query(User)
        .join(UserAssociation, UserAssociation.user_id == User.id)
        .filter(User.is_active == True)
        .distinct()
        .all()
    )