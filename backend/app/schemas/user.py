from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID
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
    fname: Optional[str] = None
    lname: Optional[str] = None
    email: Optional[EmailStr] = None
    title: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

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
    associations: list["AssociationResponse"] = []

    class Config:
        from_attributes = True