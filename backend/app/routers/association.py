# app/routers/associations.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.database import get_db
from app.models.user import User, UserRole
from app.models.association import Association, UserAssociation
from app.schemas.association import (
    AssociationCreate,
    AssociationUpdate,
    AssociationResponse,
    AssociationWithManagers,
)
from app.schemas.user import UserResponse
from app.dependencies import get_current_user, require_admin, require_super_admin

# Resolve forward reference: AssociationWithManagers.managers -> UserResponse
AssociationWithManagers.model_rebuild(_types_namespace={"UserResponse": UserResponse})

router = APIRouter(prefix="/associations", tags=["associations"])


def _serialize_association_with_managers(assoc: Association) -> dict:
    data = AssociationResponse.model_validate(assoc).model_dump()
    data["managers"] = [
        UserResponse.model_validate(ua.user).model_dump()
        for ua in assoc.managers
        if ua.user is not None
    ]
    return data


@router.get("", response_model=list[AssociationWithManagers])
def list_associations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Association).options(
        joinedload(Association.managers).joinedload(UserAssociation.user)
    )
    if current_user.role == UserRole.manager:
        # Only return associations this manager is assigned to
        assigned_ids = (
            db.query(UserAssociation.association_id)
            .filter(UserAssociation.user_id == current_user.id)
            .subquery()
        )
        query = query.filter(Association.id.in_(assigned_ids))
    associations = query.all()
    return [_serialize_association_with_managers(a) for a in associations]


@router.post("", response_model=AssociationResponse, status_code=201)
def create_association(
    body: AssociationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    assoc = Association(
        legal_name=body.legal_name,
        filter_name=body.filter_name,
        location_name=body.location_name,
    )
    db.add(assoc)
    db.commit()
    db.refresh(assoc)
    return assoc


@router.patch("/{association_id}", response_model=AssociationResponse)
def update_association(
    association_id: UUID,
    body: AssociationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    assoc = db.query(Association).filter(Association.id == association_id).first()
    if not assoc:
        raise HTTPException(status_code=404, detail="Association not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(assoc, field, value)
    db.commit()
    db.refresh(assoc)
    return assoc


@router.delete("/{association_id}", status_code=204)
def deactivate_association(
    association_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    assoc = db.query(Association).filter(Association.id == association_id).first()
    if not assoc:
        raise HTTPException(status_code=404, detail="Association not found")
    assoc.is_active = False
    db.commit()


class AssignManagerBody(BaseModel):
    user_id: UUID


@router.post("/{association_id}/managers", response_model=AssociationResponse, status_code=201)
def assign_manager(
    association_id: UUID,
    body: AssignManagerBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    assoc = db.query(Association).filter(Association.id == association_id).first()
    if not assoc:
        raise HTTPException(status_code=404, detail="Association not found")
    
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # must be at least manager role to be assigned
    if user.role not in (UserRole.manager, UserRole.admin, UserRole.super_admin):
        raise HTTPException(
            status_code=400, 
            detail="User must have at least manager role to be assigned to an association"
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Cannot assign inactive user")

    already_assigned = (
        db.query(UserAssociation)
        .filter(
            UserAssociation.user_id == body.user_id,
            UserAssociation.association_id == association_id,
        )
        .first()
    )
    if already_assigned:
        raise HTTPException(status_code=409, detail="Manager already assigned")
    
    db.add(UserAssociation(user_id=body.user_id, association_id=association_id))
    db.commit()
    db.refresh(assoc)
    return assoc


@router.delete("/{association_id}/managers/{user_id}", status_code=204)
def remove_manager(
    association_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    link = (
        db.query(UserAssociation)
        .filter(
            UserAssociation.user_id == user_id,
            UserAssociation.association_id == association_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(link)
    db.commit()
