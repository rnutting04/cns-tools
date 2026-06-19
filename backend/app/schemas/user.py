from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


# what you accept when creating a user
class UserCreate(BaseModel):
    fname: str
    lname: str
    email: EmailStr
    title: str
    role: UserRole
    password: str


# what you accept when updating a user
class UserUpdate(BaseModel):
    fname: str | None = None
    lname: str | None = None
    email: EmailStr | None = None
    title: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


# what you return in responses - notice no password_hash
class UserResponse(BaseModel):
    id: UUID
    fname: str
    lname: str
    email: str
    title: str
    role: UserRole
    is_active: bool
    password_change_required: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# what you return with associations included
class UserWithAssociations(UserResponse):
    associations: list["AssociationResponse"] = []  # noqa: F821

    class Config:
        from_attributes = True
