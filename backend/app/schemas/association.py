from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AssociationCreate(BaseModel):
    legal_name: str
    filter_name: str
    location_name: str


class AssociationUpdate(BaseModel):
    legal_name: str | None = None
    filter_name: str | None = None
    location_name: str | None = None
    is_active: bool | None = None


class AssociationResponse(BaseModel):
    id: UUID
    legal_name: str
    filter_name: str
    location_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# returned when you need managers listed under an association
class AssociationWithManagers(AssociationResponse):
    managers: list["UserResponse"] = []  # noqa: F821

    class Config:
        from_attributes = True
