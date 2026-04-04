from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class AssociationCreate(BaseModel):
    legal_name: str
    filter_name: str
    location_name: str

class AssociationUpdate(BaseModel):
    legal_name: Optional[str] = None
    filter_name: Optional[str] = None
    location_name: Optional[str] = None
    is_active: Optional[bool] = None

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
    managers: list["UserResponse"] = []

    class Config:
        from_attributes = True