# scripts/seed.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.association import Association, UserAssociation

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

def seed():
    db = SessionLocal()

    print("Clearing existing data...")
    db.query(UserAssociation).delete()
    db.query(Association).delete()
    db.query(User).delete()
    db.commit()

    print("Seeding associations...")
    sunset = Association(
        legal_name="Sunset Ridge Homeowners Association Inc.",
        filter_name="Sunset Ridge",
        location_name="Orlando, FL",
    )
    lakewood = Association(
        legal_name="Lakewood Commons Community Association",
        filter_name="Lakewood Commons",
        location_name="Tampa, FL",
    )
    pine = Association(
        legal_name="Pine Valley Residents Association",
        filter_name="Pine Valley",
        location_name="Jacksonville, FL",
    )
    maplewood = Association(
        legal_name="Maplewood Estates HOA",
        filter_name="Maplewood Estates",
        location_name="Miami, FL",
    )
    riverstone = Association(
        legal_name="Riverstone Community Association Inc.",
        filter_name="Riverstone",
        location_name="Sarasota, FL",
    )
    harbor = Association(
        legal_name="Harbor Pointe Residential Association",
        filter_name="Harbor Pointe",
        location_name="St. Petersburg, FL",
    )
    clearwater = Association(
        legal_name="Clearwater Cove HOA Inc.",
        filter_name="Clearwater Cove",
        location_name="Clearwater, FL",
    )
    magnolia = Association(
        legal_name="Magnolia Park Community Association",
        filter_name="Magnolia Park",
        location_name="Gainesville, FL",
    )
    cypress = Association(
        legal_name="Cypress Glen Homeowners Association",
        filter_name="Cypress Glen",
        location_name="Fort Lauderdale, FL",
    )
    emerald = Association(
        legal_name="Emerald Isle Residential Community",
        filter_name="Emerald Isle",
        location_name="Pensacola, FL",
    )

    all_associations = [
        sunset, lakewood, pine, maplewood, riverstone,
        harbor, clearwater, magnolia, cypress, emerald
    ]
    db.add_all(all_associations)
    db.flush()

    print("Seeding users...")

    # super admin - developer/IT level
    dev_admin = User(
        fname="System",
        lname="Admin",
        email="admin@cands.com",
        title="System Administrator",
        role=UserRole.super_admin,
        password_hash=hash_password("superadmin123"),
        is_active=True,
    )

    # admins - director/VP level
    patricia = User(
        fname="Patricia",
        lname="Williams",
        email="pwilliams@cands.com",
        title="Vice President of Operations",
        role=UserRole.admin,
        password_hash=hash_password("admin123"),
        is_active=True,
    )
    michael = User(
        fname="Michael",
        lname="Torres",
        email="mtorres@cands.com",
        title="Director of Community Management",
        role=UserRole.admin,
        password_hash=hash_password("admin123"),
        is_active=True,
    )
    sandra = User(
        fname="Sandra",
        lname="Chen",
        email="schen@cands.com",
        title="Operations Director",
        role=UserRole.admin,
        password_hash=hash_password("admin123"),
        is_active=True,
    )

    # managers - community managers assigned to associations
    jane = User(
        fname="Jane",
        lname="Smith",
        email="jsmith@cands.com",
        title="Community Manager",
        role=UserRole.manager,
        password_hash=hash_password("manager123"),
        is_active=True,
    )
    robert = User(
        fname="Robert",
        lname="Johnson",
        email="rjohnson@cands.com",
        title="Senior Community Manager",
        role=UserRole.manager,
        password_hash=hash_password("manager123"),
        is_active=True,
    )
    maria = User(
        fname="Maria",
        lname="Garcia",
        email="mgarcia@cands.com",
        title="Community Manager",
        role=UserRole.manager,
        password_hash=hash_password("manager123"),
        is_active=True,
    )
    kevin = User(
        fname="Kevin",
        lname="Patel",
        email="kpatel@cands.com",
        title="Senior Community Manager",
        role=UserRole.manager,
        password_hash=hash_password("manager123"),
        is_active=True,
    )
    lisa = User(
        fname="Lisa",
        lname="Thompson",
        email="lthompson@cands.com",
        title="Community Manager",
        role=UserRole.manager,
        password_hash=hash_password("manager123"),
        is_active=True,
    )
    carlos = User(
        fname="Carlos",
        lname="Rivera",
        email="crivera@cands.com",
        title="Community Manager",
        role=UserRole.manager,
        password_hash=hash_password("manager123"),
        is_active=True,
    )

    # inactive manager - left the company
    david = User(
        fname="David",
        lname="Brown",
        email="dbrown@cands.com",
        title="Community Manager",
        role=UserRole.manager,
        password_hash=hash_password("manager123"),
        is_active=False,
    )

    # employees - support staff, tools access only
    amy = User(
        fname="Amy",
        lname="Wallace",
        email="awallace@cands.com",
        title="Administrative Assistant",
        role=UserRole.employee,
        password_hash=hash_password("employee123"),
        is_active=True,
    )
    james = User(
        fname="James",
        lname="Mitchell",
        email="jmitchell@cands.com",
        title="Administrative Coordinator",
        role=UserRole.employee,
        password_hash=hash_password("employee123"),
        is_active=True,
    )
    rachel = User(
        fname="Rachel",
        lname="Kim",
        email="rkim@cands.com",
        title="Office Assistant",
        role=UserRole.employee,
        password_hash=hash_password("employee123"),
        is_active=True,
    )

    all_users = [
        dev_admin, patricia, michael, sandra,
        jane, robert, maria, kevin, lisa, carlos, david,
        amy, james, rachel
    ]
    db.add_all(all_users)
    db.flush()

    print("Seeding user associations...")
    # one manager per association enforced by unique constraint
    # jane      → sunset ridge, lakewood commons
    # robert    → pine valley, harbor pointe
    # maria     → maplewood estates, riverstone
    # kevin     → clearwater cove, magnolia park
    # lisa      → cypress glen
    # carlos    → emerald isle
    # patricia  → admin but also assigned to sunset ridge (vp oversight)
    # david     → inactive, was assigned to pine valley (historical)
    mappings = [
        UserAssociation(user_id=jane.id, association_id=sunset.id),
        UserAssociation(user_id=jane.id, association_id=lakewood.id),
        UserAssociation(user_id=robert.id, association_id=pine.id),
        UserAssociation(user_id=robert.id, association_id=harbor.id),
        UserAssociation(user_id=maria.id, association_id=maplewood.id),
        UserAssociation(user_id=maria.id, association_id=riverstone.id),
        UserAssociation(user_id=kevin.id, association_id=clearwater.id),
        UserAssociation(user_id=kevin.id, association_id=magnolia.id),
        UserAssociation(user_id=lisa.id, association_id=cypress.id),
        UserAssociation(user_id=carlos.id, association_id=emerald.id),
    ]
    db.add_all(mappings)
    db.commit()

    print("")
    print("Done. Summary:")
    print(f"  {db.query(Association).count()} associations")
    print(f"  {db.query(User).count()} total users")
    print(f"  {db.query(User).filter(User.role == UserRole.super_admin).count()} super admins")
    print(f"  {db.query(User).filter(User.role == UserRole.admin).count()} admins")
    print(f"  {db.query(User).filter(User.role == UserRole.manager).count()} managers")
    print(f"  {db.query(User).filter(User.role == UserRole.employee).count()} employees")
    print(f"  {db.query(User).filter(User.is_active == False).count()} inactive users")
    print(f"  {db.query(UserAssociation).count()} manager assignments")
    print("")
    print("Test credentials:")
    print("  super_admin  admin@cands.com       superadmin123")
    print("  admin        pwilliams@cands.com   admin123")
    print("  admin        mtorres@cands.com     admin123")
    print("  manager      jsmith@cands.com      manager123  (2 associations)")
    print("  manager      rjohnson@cands.com    manager123  (2 associations)")
    print("  manager      kpatel@cands.com      manager123  (2 associations)")
    print("  employee     awallace@cands.com    employee123 (no associations)")
    print("  inactive     dbrown@cands.com      manager123  (login rejected)")
    db.close()

if __name__ == "__main__":
    seed()