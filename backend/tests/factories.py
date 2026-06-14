"""
Lightweight data factories for tests.

Each helper inserts a row and flushes (not commits) so it participates in the
per-test transaction that ``db_session`` rolls back. Reuses the production
``hash_password`` so password-verification paths behave like real users.
"""

import itertools
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.association import Association, UserAssociation
from app.models.template import Template
from app.models.user import User, UserRole
from app.utils.auth import hash_password

# Default plaintext password for created users. Tests that exercise login use
# this so they can authenticate; it satisfies the >=12 char policy.
DEFAULT_PASSWORD = "TestPassw0rd!"

_email_counter = itertools.count(1)


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{next(_email_counter)}-{uuid4().hex[:6]}@example.com"


def create_user(
    db: Session,
    *,
    email: str | None = None,
    fname: str = "Test",
    lname: str = "User",
    title: str = "Manager",
    role: UserRole = UserRole.manager,
    password: str = DEFAULT_PASSWORD,
    password_change_required: bool = False,
    is_active: bool = True,
) -> User:
    user = User(
        email=email or _unique_email(),
        fname=fname,
        lname=lname,
        title=title,
        role=role,
        password_hash=hash_password(password),
        password_change_required=password_change_required,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def create_association(
    db: Session,
    *,
    legal_name: str = "Sunset Ridge Homeowners Association, Inc.",
    filter_name: str = "Sunset Ridge",
    location_name: str = "Bradenton",
    is_active: bool = True,
) -> Association:
    assoc = Association(
        legal_name=legal_name,
        filter_name=filter_name,
        location_name=location_name,
        is_active=is_active,
    )
    db.add(assoc)
    db.flush()
    return assoc


def assign_manager(db: Session, user: User, association: Association) -> UserAssociation:
    link = UserAssociation(user_id=user.id, association_id=association.id)
    db.add(link)
    db.flush()
    return link


def create_template(
    db: Session,
    *,
    name: str = "Annual Meeting Notice",
    category: str = "Notices",
    docx_path: str = "templates/annual-meeting-notice.docx",
    fields: list | None = None,
    renderer_type: str = "simple",
    is_active: bool = True,
) -> Template:
    template = Template(
        name=name,
        category=category,
        docx_path=docx_path,
        fields=fields if fields is not None else [],
        renderer_type=renderer_type,
        is_active=is_active,
    )
    db.add(template)
    db.flush()
    return template
