# scripts/seed.py
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from dotenv import load_dotenv

from app.config.settings import ENV_FILE

# The app reads .env through pydantic-settings, which populates the Settings
# object but never exports anything into os.environ. The seed passwords are also
# not declared as Settings fields (and Config.extra = "ignore" drops them), so
# without this they are unreachable from both places even when set in .env.
# Loading the same ENV_FILE keeps the two from drifting apart.
load_dotenv(ENV_FILE)

from app.database import SessionLocal
from app.models.association import Association, UserAssociation
from app.models.budget_job import BudgetJob
from app.models.letter_job import LetterJob
from app.models.user import User, UserRole


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed():
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
    manager_password = os.environ.get("SEED_MANAGER_PASSWORD")

    if not admin_password or not manager_password:
        missing = [
            name
            for name, value in (
                ("SEED_ADMIN_PASSWORD", admin_password),
                ("SEED_MANAGER_PASSWORD", manager_password),
            )
            if not value
        ]
        print(f"ERROR: {' and '.join(missing)} must be set.")
        print(f"Looked in the environment and in {ENV_FILE} (exists: {ENV_FILE.exists()}).")
        sys.exit(1)

    db = SessionLocal()

    print("Clearing existing data...")
    db.query(BudgetJob).delete()
    db.query(LetterJob).delete()
    db.query(UserAssociation).delete()
    db.query(Association).delete()
    db.query(User).delete()
    db.commit()

    print("Seeding users...")
    mgr_pw = hash_password(manager_password)

    # Keyed by old integer manager ID for mapping association_manager rows below.
    users = {
        16: User(
            fname="Dana",
            lname="Cloer McGann",
            email="Dcloer@cscmsi.com",
            title="CAM CMCA",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        17: User(
            fname="M. H. Chris",
            lname="Brown",
            email="Cbrown@cscmsi.com",
            title="CAM CMCA AMS PCAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        18: User(
            fname="Ellen",
            lname="Brown Martinez",
            email="Ebrown@cscmsi.com",
            title="CAM CMCA AMS PCAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        20: User(
            fname="Janet",
            lname="Fernandez",
            email="jfernandez@cscmsi.com",
            title="CAM CMCA AMS PCAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        21: User(
            fname="Betsy",
            lname="Davis",
            email="bdavis@cscmsi.com",
            title="CAM CMCA",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        22: User(
            fname="Bill",
            lname="McGann",
            email="bmcgann@cscmsi.com",
            title="CAM CMCA",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        24: User(
            fname="Salvatore",
            lname="Muno",
            email="smuno@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        27: User(
            fname="Julie",
            lname="Conway",
            email="jconway@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        28: User(
            fname="Jamie",
            lname="McCormick",
            email="jmccormick@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        29: User(
            fname="Terry",
            lname="Lewis",
            email="tlewis@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        30: User(
            fname="Judi",
            lname="Morrison",
            email="jmorrison@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        31: User(
            fname="Nicole",
            lname="Grier",
            email="ngrier@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        32: User(
            fname="Kasia",
            lname="Matt",
            email="kmatt@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        33: User(
            fname="Jennifer",
            lname="Johnson",
            email="jjohnson@cscmsi.com",
            title="CAM CFCAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        35: User(
            fname="Alexia",
            lname="Gamundi",
            email="agamundi@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        38: User(
            fname="Anthony",
            lname="DiBiagio",
            email="adibiagio@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        49: User(
            fname="Marisol",
            lname="Ramsey",
            email="mramsey@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        50: User(
            fname="Daniel",
            lname="Shepard",
            email="dshepard@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        51: User(
            fname="Danielle",
            lname="Monroe",
            email="dmonroe@cscmsi.com",
            title="CAM JD MBA",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        52: User(
            fname="Jennifer",
            lname="Trullinger",
            email="jtrullinger@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
        53: User(
            fname="Ivy",
            lname="Kaull",
            email="ikaull@cscmsi.com",
            title="CAM",
            role=UserRole.manager,
            password_hash=mgr_pw,
            is_active=True,
        ),
    }

    admin = User(
        fname="System",
        lname="Admin",
        email="admin@cscmsi.com",
        title="System Administrator",
        role=UserRole.super_admin,
        password_hash=hash_password(admin_password),
        is_active=True,
    )

    db.add_all(list(users.values()) + [admin])
    db.flush()

    print("Seeding associations...")
    # Keyed by old integer association ID for mapping association_manager rows below.
    assocs = {
        51: Association(
            legal_name="Mar Cove Condominium Association, Inc",
            filter_name="Mar Cove",
            location_name="Cortez",
        ),
        52: Association(
            legal_name="Cove Pointe Condominium Association, Inc",
            filter_name="Cove Pointe",
            location_name="Cortez",
        ),
        53: Association(
            legal_name="Oakwood Villas Condominium Owners Association, Inc",
            filter_name="Oakwood Villas",
            location_name="Bradenton",
        ),
        54: Association(
            legal_name="Martinique North Condominium Association, Inc",
            filter_name="Martinique North",
            location_name="Holmes Beach",
        ),
        55: Association(
            legal_name="Palms at Palma Sola Homeowners Association, Inc",
            filter_name="Palms at Palma Sola",
            location_name="Bradenton",
        ),
        56: Association(
            legal_name="The Palms at Riviera Dunes Condominium Association, Inc",
            filter_name="The Palms at Riviera Dunes",
            location_name="Palmetto",
        ),
        58: Association(
            legal_name="Riverview Landings Community Association, Inc",
            filter_name="Riverview Landings",
            location_name="Bradenton",
        ),
        59: Association(
            legal_name="Villa Valencia Garden Condominium Association, Inc",
            filter_name="Villa Valencia",
            location_name="St. Petersberg",
        ),
        60: Association(
            legal_name="The Estates at Glenn Lakes Owners Association, Inc",
            filter_name="Estates at Glenn Lakes",
            location_name="Bradenton",
        ),
        61: Association(
            legal_name="Woodpark at Desoto Sqaure Owners' Association, Inc",
            filter_name="Woodpark",
            location_name="Bradenton",
        ),
        62: Association(
            legal_name="Owners' Association at North Beach Village, Inc",
            filter_name="North Beach Village",
            location_name="Holmes Beach",
        ),
        63: Association(
            legal_name="The Third Bayshore, Condominium Association, Inc",
            filter_name="Third Bayshore",
            location_name="Bradenton",
        ),
        64: Association(
            legal_name="Hawthorn Park Community Association, Inc",
            filter_name="Hawthorn Park",
            location_name="Bradenton",
        ),
        65: Association(
            legal_name="The Harbor Villas at Dona Bay Condominium Association, Inc",
            filter_name="Harbor Villas at Dona Bay",
            location_name="Nokomis",
        ),
        66: Association(
            legal_name="Condominium Owners Association of Meadowcroft South, Inc",
            filter_name="Meadowcroft South",
            location_name="Bradenton",
        ),
        67: Association(
            legal_name="The Crossings Maintenance Association, Inc",
            filter_name="The Crossings",
            location_name="Bradenton",
        ),
        68: Association(
            legal_name="Hidden Lake of Manatee Owners' Association, Inc",
            filter_name="Hidden Lake of Manatee",
            location_name="Bradenton",
        ),
        69: Association(
            legal_name="Del Tierra Homeowners' Association, Inc",
            filter_name="Del Tierra",
            location_name="Bradenton",
        ),
        71: Association(
            legal_name="Baywood Colony Southwood Apartments 1 Condominium Association Inc",
            filter_name="Baywood Colony 1",
            location_name="Sarasota",
        ),
        73: Association(
            legal_name="Landings South VI Condominium Association Inc",
            filter_name="Landings South VI",
            location_name="Sarasota",
        ),
        74: Association(
            legal_name="Crooked Creek Owners Association Inc",
            filter_name="Crooked Creek",
            location_name="Sarasota",
        ),
        77: Association(
            legal_name="Crooked Creek III at Sarasota National Condominium Association Inc",
            filter_name="Crooked Creek III at Sarasota",
            location_name="Venice",
        ),
        78: Association(
            legal_name="Crooked Creek IV at Sarasota National Condominium Association Inc",
            filter_name="Crooked Creek IV at Sarasota",
            location_name="Venice",
        ),
        79: Association(
            legal_name="Mark Twain Association Inc",
            filter_name="Mark Twain",
            location_name="Sarasota",
        ),
        80: Association(
            legal_name="South Gate Village Green Section 11 Condominium Association Inc",
            filter_name="South Gate Village Green Section 11",
            location_name="Sarasota",
        ),
        81: Association(
            legal_name="Amber Glen Community Association Inc",
            filter_name="Amber Glen",
            location_name="Palmetto",
        ),
        82: Association(
            legal_name="Carpentras at the Villages of Avignon",
            filter_name="Carpentras at the Villages of Avignon",
            location_name="Palmetto",
        ),
        83: Association(
            legal_name="Desoto Square Villas Owners' Association Inc",
            filter_name="Desoto Square Villas",
            location_name="Bradenton",
        ),
        85: Association(
            legal_name="Heron Creek Neighborhood Association Inc",
            filter_name="Heron Creek",
            location_name="Palmetto",
        ),
        86: Association(
            legal_name="Peridia Patio Homeowners' 6 Association Inc",
            filter_name="Peridia Patio 6",
            location_name="Bradenton",
        ),
        87: Association(
            legal_name="River Place Property Owners' Association Inc",
            filter_name="River Place",
            location_name="Bradenton",
        ),
        88: Association(
            legal_name="Sun Plaza West Condominium Association Inc",
            filter_name="Sun Plaza West",
            location_name="Holmes Beach",
        ),
        89: Association(
            legal_name="Ten Downing Street Condominium Association Inc",
            filter_name="Ten Downing",
            location_name="Palmetto",
        ),
        90: Association(
            legal_name="Willow Walk Community Association Inc",
            filter_name="Willow Walk",
            location_name="Palmetto",
        ),
        91: Association(
            legal_name="Bayview of Bradenton Beach Condominium Association, Inc",
            filter_name="Bayview of Bradenton Beach",
            location_name="Bradenton Beach",
        ),
        93: Association(
            legal_name="Cordova Villas Condominium Association, Inc",
            filter_name="Cordova Villas",
            location_name="Bradenton",
        ),
        95: Association(
            legal_name="Groveland Home Owners Association, Inc",
            filter_name="Groveland",
            location_name="Bradenton",
        ),
        97: Association(
            legal_name="North Point Harbour Community Association, Inc",
            filter_name="North Point Harbour",
            location_name="Holmes Beach",
        ),
        100: Association(
            legal_name="Vivienda at Bradenton I Condominium Association, Inc",
            filter_name="Vivienda at Bradenton I",
            location_name="Bradenton",
        ),
        101: Association(
            legal_name="Fair Lane Acres, Inc",
            filter_name="Fair Lane Acres",
            location_name="Bradenton",
        ),
        102: Association(
            legal_name="Village of Bayshore Garden Condominium Association, Inc",
            filter_name="Village of Bayshore Garden",
            location_name="Bradenton",
        ),
        103: Association(
            legal_name="Island Village Condominium Association of Holmes Beach, Inc",
            filter_name="Island Village",
            location_name="Holmes Beach",
        ),
        104: Association(
            legal_name="Hidden Lake Village of Sarasota, Inc",
            filter_name="Hidden Lake Village",
            location_name="Sarasota",
        ),
        105: Association(
            legal_name="Cedar Coves Estates Property Owners' Association, Inc",
            filter_name="Cedar Coves Estates",
            location_name="Sarasota",
        ),
        106: Association(
            legal_name="Sea Pines Condominium Association, Inc",
            filter_name="Sea Pines",
            location_name="Longboat Key",
        ),
        107: Association(
            legal_name="The Links of Palm-Aire Community Association, Inc",
            filter_name="The Links of Palm-Aire",
            location_name="Sarasota",
        ),
        109: Association(
            legal_name="Sarabay Woods Homeowners' Association, Inc",
            filter_name="Sarabay Woods",
            location_name="Sarasota",
        ),
        110: Association(
            legal_name="Waterford Condomnium Association, Inc",
            filter_name="Waterford",
            location_name="Palmetto",
        ),
        111: Association(
            legal_name="River Point of Manatee Home Owners Association, Inc",
            filter_name="River Pointe of Manatee",
            location_name="Bradenton",
        ),
        112: Association(
            legal_name="Palma Sola Trace Condominium Association, Inc",
            filter_name="Palma Sola Trace Condo",
            location_name="Bradenton",
        ),
        113: Association(
            legal_name="Riggs Landing Condominium Association, Inc",
            filter_name="Riggs Landing",
            location_name="Sarasota",
        ),
        114: Association(
            legal_name="5400 Gulf Drive Inc, A Condominium",
            filter_name="5400 Gulf Drive",
            location_name="Holmes Beach",
        ),
        115: Association(
            legal_name="Bay Club Association, Inc", filter_name="Bay Club", location_name="Palmetto"
        ),
        116: Association(
            legal_name="Bay Lake Estates Association, Inc",
            filter_name="Bay Lake Estates",
            location_name="Bradenton",
        ),
        118: Association(
            legal_name="Foxbrook Homeowners' Association, Inc",
            filter_name="Foxbrook",
            location_name="Parrish",
        ),
        119: Association(
            legal_name="Pebble Springs Condominium Association of Bradenton, Inc",
            filter_name="Pebble Springs",
            location_name="Bradenton",
        ),
        120: Association(
            legal_name="Sabal Harbour Homeowners' Association, Inc",
            filter_name="Sabal Harbour",
            location_name="Bradenton",
        ),
        121: Association(
            legal_name="Ironwood First Condominium Association, Inc",
            filter_name="Ironwood First",
            location_name="Bradenton",
        ),
        122: Association(
            legal_name="Ironwood Second Condominium Association, Inc",
            filter_name="Ironwood Second",
            location_name="Bradenton",
        ),
        123: Association(
            legal_name="Martinique South Condominium Association, Inc",
            filter_name="Martinique South",
            location_name="Holmes Beach",
        ),
        124: Association(
            legal_name="The Fairways Two at Pinebrook Owners' Association, Inc",
            filter_name="Fairways Two at Pinebrook",
            location_name="Bradenton",
        ),
        125: Association(
            legal_name="The Links at Pinebrook Owners' Association, Inc",
            filter_name="The Links at Pinebrook",
            location_name="Bradenton",
        ),
        126: Association(
            legal_name="Fairways at Imperial Lakewoods Phase 1A-1 Homeowners' Association, Inc",
            filter_name="Fairways at Imperial Lakewoods",
            location_name="Palmetto",
        ),
        127: Association(
            legal_name="Forest Creek Community Association, Inc",
            filter_name="Forest Creek",
            location_name="Parrish",
        ),
        128: Association(
            legal_name="Greenbrook Walk Condominium Association, Inc",
            filter_name="Greenbrook Walk",
            location_name="Bradenton",
        ),
        129: Association(
            legal_name="Miramar at Lakewood Ranch Condominium Association, Inc",
            filter_name="Miramar at Lakewood Ranch",
            location_name="Lakewood Ranch",
        ),
        130: Association(
            legal_name="Highland Lakes/Bradenton Owners' Association, Inc",
            filter_name="Highland Lakes",
            location_name="Bradenton",
        ),
        131: Association(
            legal_name="The Village at Beekman Place Condominium Association, Inc",
            filter_name="Village at Beekman Place",
            location_name="Sarasota",
        ),
        132: Association(
            legal_name="Morton Village Condominium Association, Inc",
            filter_name="Morton Village",
            location_name="Bradenton",
        ),
        133: Association(
            legal_name="Braden River Lakes Master Association, Inc",
            filter_name="Braden River Lakes",
            location_name="Bradenton",
        ),
        135: Association(
            legal_name="Courtyard Square Condominium Association Inc",
            filter_name="Courtyard Square",
            location_name="Bradenton",
        ),
        137: Association(
            legal_name="Grande Oaks Preserve Condominium Association, Inc",
            filter_name="Grande Oaks Preserve",
            location_name="Sarasota",
        ),
        139: Association(
            legal_name="Moss Creek Property Owner's Association, Inc",
            filter_name="Moss Creek",
            location_name="Bradenton",
        ),
        140: Association(
            legal_name="Anna Maria Island Club Condominium Association Inc",
            filter_name="Anna Maria Island Club",
            location_name="Bradenton Beach",
        ),
        141: Association(
            legal_name="Cambridge Village West Condominium Owners Association Inc",
            filter_name="Cambridge Village West",
            location_name="Bradenton",
        ),
        142: Association(
            legal_name="The Estuaries Condominium Owners Association Inc",
            filter_name="The Estuaries",
            location_name="Palmetto",
        ),
        143: Association(
            legal_name="Hammocks at Riviera Dunes Association Inc",
            filter_name="Hammocks at Riviera Dunes",
            location_name="Palmetto",
        ),
        144: Association(
            legal_name="Lakeside South Property Owners Association Inc",
            filter_name="Lakeside South",
            location_name="Bradenton",
        ),
        145: Association(
            legal_name="Preserve Community Association Inc",
            filter_name="Preserve Community",
            location_name="Bradenton",
        ),
        146: Association(
            legal_name="Palma Sola Trace Villas Homeowners Association Inc",
            filter_name="Palma Sola Trace Villas",
            location_name="Bradenton",
        ),
        148: Association(
            legal_name="Summer Sands Condominium Association Inc",
            filter_name="Summer Sands",
            location_name="Bradenton Beach",
        ),
        149: Association(
            legal_name="Stoneledge Homeowners Association Inc",
            filter_name="Stoneledge",
            location_name="Bradenton",
        ),
        150: Association(
            legal_name="Woodland Village Condominium Association Inc",
            filter_name="Woodland Village",
            location_name="Bradenton",
        ),
        151: Association(
            legal_name="Coach Homes VI at River Strand, A Phase Condominium",
            filter_name="Coach Homes IV",
            location_name="Bradenton",
        ),
        152: Association(
            legal_name="Fairway Gardens II at Tara, A Condominium",
            filter_name="Fairway Gardens II",
            location_name="Bradenton",
        ),
        153: Association(
            legal_name="Gulf Gate Garden Homes East",
            filter_name="Gulf Gate Garden Homes East",
            location_name="Sarasota",
        ),
        154: Association(
            legal_name="Manatee Oaks Homeowners Association, Inc",
            filter_name="Manatee Oaks",
            location_name="Bradenton",
        ),
        155: Association(
            legal_name="Regency Oaks Homeowners Association, Inc",
            filter_name="Regency Oaks",
            location_name="Palmetto",
        ),
        157: Association(
            legal_name="Runaway Bay Condominium",
            filter_name="Runaway Bay",
            location_name="Bradenton Beach",
        ),
        158: Association(
            legal_name="Stone Harbour Commons",
            filter_name="Stone Harbour Commons",
            location_name="Bradenton",
        ),
        159: Association(
            legal_name="Stone Harbor I, A Condominium",
            filter_name="Stone Harbour I",
            location_name="Bradenton",
        ),
        160: Association(
            legal_name="Stone Harbor II, A Condominium",
            filter_name="Stone Harbour II",
            location_name="Bradenton",
        ),
        161: Association(
            legal_name="Stone Harbor III, A Condominium",
            filter_name="Stone Harbour III",
            location_name="Bradenton",
        ),
        162: Association(
            legal_name="Veranda II at River Strand, A Phase Condominium",
            filter_name="Veranda II",
            location_name="Bradenton",
        ),
        163: Association(
            legal_name="The Waterway, A Condominium",
            filter_name="The Waterway",
            location_name="Bradenton",
        ),
        166: Association(
            legal_name="Westbay Cove Association, Inc",
            filter_name="Westbay Cove",
            location_name="Holmes Beach",
        ),
        167: Association(
            legal_name="1500 State Street Condominium Association, Inc",
            filter_name="1500 State Street",
            location_name="Sarasota",
        ),
        168: Association(
            legal_name="Jacaranda Commercial Center Property Owners Association, Inc",
            filter_name="Jacaranda Commercial Center",
            location_name="Venice",
        ),
        170: Association(
            legal_name="Cottages at San Casciano Homeowners Association, Inc",
            filter_name="Cottages at San Casciano",
            location_name="Bradenton",
        ),
        171: Association(
            legal_name="Fruitville Professional Office Center Condominium Association Inc",
            filter_name="Fruitville Professional",
            location_name="Sarasota",
        ),
        172: Association(
            legal_name="Gulf Gate East Homeowners' Association, Inc",
            filter_name="Gulf Gate East",
            location_name="Sarasota",
        ),
        173: Association(
            legal_name="Heather Glen Property Owners' I Association, Inc",
            filter_name="Heather Glen",
            location_name="Palmetto",
        ),
        174: Association(
            legal_name="The Island Condominium Association, Inc",
            filter_name="Island Condo",
            location_name="Sarasota",
        ),
        175: Association(
            legal_name="McIntosh Meadows Association, Inc",
            filter_name="McIntosh Meadows",
            location_name="Sarasota",
        ),
        176: Association(
            legal_name="Oak Ford Gulf Club Owners Association, Inc",
            filter_name="Oak Ford Gulf Club",
            location_name="Sarasota",
        ),
        177: Association(
            legal_name="Palm Breeze Villas Condominium Association, Inc",
            filter_name="Palm Breeze Villas",
            location_name="Bradenton",
        ),
        178: Association(
            legal_name="Riviera Club Village Homeowner Association, Inc",
            filter_name="Riviera Club Village",
            location_name="Sarasota",
        ),
        179: Association(
            legal_name="624 Palm Condominium",
            filter_name="624 Palm Condominium",
            location_name="Sarasota",
        ),
        180: Association(
            legal_name="Buckingham Meadows II of St Andrews East at The Plantation, a Condominium",
            filter_name="Buckingham Meadows II",
            location_name="Venice",
        ),
        181: Association(
            legal_name="Westminster Glen of St Andrews East at The Plantation, a Condominium",
            filter_name="Westminster Glen",
            location_name="Venice",
        ),
        182: Association(
            legal_name="Carlyle Community Association, Inc",
            filter_name="Carlyle",
            location_name="Sarasota",
        ),
        183: Association(
            legal_name="Palisades at Palmer Ranch, Inc, a Land Condominium",
            filter_name="Palisades at Palmer Ranch",
            location_name="Sarasota",
        ),
        184: Association(
            legal_name="Mira Lago Community Association, Inc",
            filter_name="Mira Lago",
            location_name="Sarasota",
        ),
        185: Association(
            legal_name="Fiddler's Green Condominium I, a Condominium",
            filter_name="Fiddlers Green",
            location_name="Englewood",
        ),
        186: Association(
            legal_name="Botanica Community Association",
            filter_name="Botanica",
            location_name="Sarasota",
        ),
        187: Association(
            legal_name="Bouchard Gardens, a Condominium",
            filter_name="Bouchard Gardens",
            location_name="Sarasota",
        ),
        188: Association(
            legal_name="Provence Gardens, a Condominium",
            filter_name="Provence Gardens",
            location_name="Sarasota",
        ),
        189: Association(
            legal_name="Parisienne Gardens, a Condominium",
            filter_name="Parisienne Gardens",
            location_name="Sarasota",
        ),
        190: Association(
            legal_name="Pinehurst Village, Section One, a Condominium",
            filter_name="Pinehurst Village, Section One",
            location_name="Sarasota",
        ),
        192: Association(
            legal_name="Sun Isle Condominium Association of Bradenton Beach, Inc",
            filter_name="Sun Isle of Bradenton Beach",
            location_name="Holmes Beach",
        ),
        193: Association(
            legal_name="Seacrest Two Condominium Association, Inc",
            filter_name="Seacrest Two",
            location_name="Holmes Beach",
        ),
        196: Association(
            legal_name="Ironwood Eleven Condominium Associaiton, Inc",
            filter_name="Ironwood Eleven",
            location_name="Bradenton",
        ),
        197: Association(
            legal_name="Pinebrook Condominium Association, Inc",
            filter_name="Pinebrook Condo",
            location_name="Bradenton",
        ),
        198: Association(
            legal_name="Sarasota Eastpointe Homeowners Associaiton, Inc",
            filter_name="Sarasota Eastpointe",
            location_name="Sarasota",
        ),
        199: Association(
            legal_name="Fiddler's Bend Condominium Association, Inc",
            filter_name="Fiddler's Bend",
            location_name="Palmetto",
        ),
        200: Association(
            legal_name="The Cottages at San Lorenzo Homeowners' Association, Inc",
            filter_name="The Cottages at San Lorenzo",
            location_name="Bradenton",
        ),
        201: Association(
            legal_name="Country Meadows Community Association, Inc",
            filter_name="Country Meadows",
            location_name="Bradenton",
        ),
        204: Association(
            legal_name="Gillette Grove Homeowner's Association, Inc",
            filter_name="Gillette Grove",
            location_name="Sarasota",
        ),
        205: Association(
            legal_name="Heritage Oaks Homeowners Association, Inc",
            filter_name="Heritage Oaks",
            location_name="Sarasota",
        ),
        206: Association(
            legal_name="Lakeside Preserve Homeowners' Association, Inc",
            filter_name="Lakeside Preserve",
            location_name="Parrish",
        ),
        207: Association(
            legal_name="Lionshead Homeowners' Association, Inc",
            filter_name="Lionshead",
            location_name="Bradenton",
        ),
        208: Association(
            legal_name="River Sound Homeowner's Association, Inc",
            filter_name="River Sound",
            location_name="Bradenton",
        ),
        210: Association(
            legal_name="Valgo Association II, Inc",
            filter_name="Valgo II",
            location_name="Bradenton",
        ),
        211: Association(
            legal_name="Village Green of Bradenton Condominium, Sention 8, Association, Inc",
            filter_name="Village Green Section 8",
            location_name="Bradenton",
        ),
        212: Association(
            legal_name="West Glenn Owners Association, Inc",
            filter_name="West Glenn",
            location_name="Bradenton",
        ),
        213: Association(
            legal_name="Arbor Oaks Property Owners Association, Inc",
            filter_name="Arbor Oaks",
            location_name="Bradenton",
        ),
        215: Association(
            legal_name="Park Place of Manatee County Homeowners' Association, Inc",
            filter_name="Park Place",
            location_name="Bradenton",
        ),
        216: Association(
            legal_name="Clubhouse Verandas of Tara Association, Inc",
            filter_name="Clubhouse Verandas of Tara",
            location_name="Bradenton",
        ),
        217: Association(
            legal_name="Beach View of Manatee Condominium Association, Inc",
            filter_name="Beach View of Manatee",
            location_name="Bradenton Beach",
        ),
        218: Association(
            legal_name="Sandy Pointe of Manatee County Condominium Association, Inc",
            filter_name="Sandy Pointe",
            location_name="Holmes Beach",
        ),
        219: Association(
            legal_name="Fountain Lake Association, Inc",
            filter_name="Fountain Lake",
            location_name="Bradenton",
        ),
        220: Association(
            legal_name="The Villas at Pinebrook Owners' Association, Inc",
            filter_name="Villas at Pinebrook",
            location_name="Bradenton",
        ),
        221: Association(
            legal_name="The Villas of Pointe West Condominium Owners Association, Inc",
            filter_name="Villas of Pointe West",
            location_name="Bradenton",
        ),
        222: Association(
            legal_name="Chelsea Oaks Homeowners Associations, Inc",
            filter_name="Chelsea Oaks",
            location_name="Parrish",
        ),
        223: Association(
            legal_name="Glen Oaks Ridge Owners Condominium Association, Inc",
            filter_name="Glen Oaks Ridge",
            location_name="Sarasota",
        ),
        225: Association(
            legal_name="Oak Run III at Sarasota National Condominium Association, Inc",
            filter_name="Oak Run III",
            location_name="Venice",
        ),
        226: Association(
            legal_name="The Fairways at Pinebrook Owner's Association, Inc.",
            filter_name="Fairways at Pinebrook",
            location_name="Bradenton",
        ),
        227: Association(
            legal_name="Marbella Community Association, Inc.",
            filter_name="Marbella",
            location_name="Sarasota",
        ),
        228: Association(
            legal_name="Hidden Bay Neighborhood Association, Inc.",
            filter_name="Hidden Bay",
            location_name="Osprey",
        ),
        229: Association(
            legal_name="Harbour Walk Homeowners' Association, Inc.",
            filter_name="Harbour Walk",
            location_name="Bradenton",
        ),
        231: Association(
            legal_name="Oak Run III at Sarasota National Condominium Association, Inc.",
            filter_name="Oak Run III at Sarasota Nat'l",
            location_name="Venice",
        ),
        232: Association(
            legal_name="Veranda VI at Lakewood National Condominium Association, Inc.",
            filter_name="Veranda VI at Lakewood National",
            location_name="Lakewood Ranch",
        ),
        233: Association(
            legal_name="Rivers Edge Homeowners' Association of Manatee County, Inc.",
            filter_name="Rivers Edge",
            location_name="Bradenton",
        ),
        541: Association(
            legal_name="Fairway Gardens at Tara Condominium Association, Inc.",
            filter_name="Fairway Gardens at Tara",
            location_name="Bradenton",
        ),
        611: Association(legal_name="Banbury", filter_name="Banbury", location_name="Venice"),
        612: Association(
            legal_name="Wallingford Homeowners Association, Inc.",
            filter_name="Wallingford",
            location_name="Bradenton",
        ),
        613: Association(
            legal_name="Waterford Community Association, Inc.",
            filter_name="Waterford Community",
            location_name="Palmetto",
        ),
        614: Association(
            legal_name="PALISADES COMMUNITY ASSOCIATION, INC.",
            filter_name="Palisades Community",
            location_name="Bradenton",
        ),
        615: Association(
            legal_name="Cottages at San Lorenzo Homeowners' Association, Inc.",
            filter_name="Cottages at San Lorenzo",
            location_name="Bradenton",
        ),
        616: Association(
            legal_name="Eagle Creek Recreation Association Inc.",
            filter_name="Eagle Creek",
            location_name="Sarasota",
        ),
        617: Association(
            legal_name="Porto Vista Combined Condominium Association, Inc.",
            filter_name="Porto Vista Combined",
            location_name="Venice",
        ),
        618: Association(
            legal_name="Porto Vista Master Property Owners Association, Inc.",
            filter_name="Porto Vista Master",
            location_name="Venice",
        ),
        619: Association(
            legal_name="Orchid Oaks Condominium Association, Inc.",
            filter_name="Orchid Oaks",
            location_name="Sarasota",
        ),
        620: Association(
            legal_name="Grand Estuary IV at River Strand Condominium Association, Inc.",
            filter_name="Grand Estuary IV",
            location_name="Bradenton",
        ),
        621: Association(
            legal_name="Riva Trace Homeowners Associations, Inc.",
            filter_name="Riva Trace",
            location_name="Sarasota",
        ),
        622: Association(
            legal_name="Terrace V at Lakewood National Condominium Association, Inc.",
            filter_name="Terrace V",
            location_name="Lakewood Ranch",
        ),
        623: Association(
            legal_name="Terrace VIII at Lakewood National Condominium Association, Inc.",
            filter_name="Terrace VIII",
            location_name="Lakewood Ranch",
        ),
        624: Association(
            legal_name="The Meadows Springlake Condominium Association, Inc.",
            filter_name="Springlake",
            location_name="Sarasota",
        ),
        625: Association(
            legal_name="The Ringling Garden Apartments Association, Inc.",
            filter_name="Ringling Garden",
            location_name="Sarasota",
        ),
        626: Association(
            legal_name="Meadowlake Condominium Association, Inc,",
            filter_name="Meadowlake",
            location_name="Sarasota",
        ),
        627: Association(
            legal_name="The Meadows Springlake Condominium Association,Inc.",
            filter_name="Meadows",
            location_name="Sarasota",
        ),
        628: Association(
            legal_name="Grand Estuary V at River Strand Condominium Association, Inc.",
            filter_name="Grand Estuary V",
            location_name="Bradenton",
        ),
    }

    db.add_all(list(assocs.values()))
    db.flush()

    print("Seeding user associations...")
    # Tuples of (association_old_id, manager_old_id) from the original association_manager table.
    raw_mappings = [
        (213, 51),
        (216, 51),
        (215, 51),
        (102, 51),
        (111, 51),
        (55, 16),
        (56, 16),
        (58, 16),
        (59, 16),
        (68, 16),
        (123, 16),
        (223, 16),
        (51, 16),
        (52, 16),
        (53, 16),
        (54, 16),
        (66, 16),
        (67, 16),
        (151, 50),
        (628, 50),
        (103, 50),
        (83, 50),
        (611, 50),
        (74, 50),
        (196, 50),
        (625, 50),
        (60, 18),
        (61, 18),
        (62, 18),
        (64, 18),
        (65, 18),
        (78, 18),
        (121, 21),
        (122, 21),
        (124, 21),
        (125, 21),
        (126, 21),
        (127, 21),
        (128, 21),
        (129, 21),
        (130, 21),
        (131, 21),
        (132, 21),
        (133, 21),
        (197, 21),
        (221, 38),
        (97, 38),
        (91, 38),
        (226, 38),
        (73, 38),
        (198, 38),
        (80, 38),
        (620, 38),
        (95, 38),
        (114, 20),
        (115, 20),
        (116, 20),
        (118, 20),
        (119, 20),
        (112, 20),
        (217, 52),
        (199, 52),
        (219, 52),
        (120, 52),
        (218, 52),
        (148, 52),
        (220, 52),
        (109, 24),
        (110, 24),
        (113, 24),
        (541, 24),
        (227, 24),
        (225, 24),
        (622, 24),
        (623, 24),
        (77, 24),
        (79, 24),
        (231, 24),
        (232, 24),
        (616, 24),
        (69, 53),
        (101, 17),
        (193, 17),
        (192, 17),
        (81, 22),
        (82, 22),
        (85, 22),
        (86, 22),
        (87, 22),
        (88, 22),
        (89, 22),
        (90, 22),
        (614, 22),
        (626, 22),
        (104, 29),
        (105, 29),
        (106, 29),
        (107, 29),
        (71, 29),
        (100, 29),
        (135, 30),
        (137, 30),
        (139, 30),
        (228, 30),
        (172, 30),
        (200, 30),
        (612, 30),
        (615, 30),
        (617, 30),
        (618, 30),
        (140, 27),
        (141, 27),
        (142, 27),
        (143, 27),
        (144, 27),
        (145, 27),
        (146, 27),
        (149, 27),
        (150, 27),
        (624, 27),
        (627, 27),
        (152, 31),
        (154, 31),
        (155, 31),
        (157, 31),
        (158, 31),
        (159, 31),
        (160, 31),
        (161, 31),
        (162, 31),
        (163, 31),
        (166, 31),
        (153, 31),
        (613, 31),
        (168, 32),
        (170, 32),
        (171, 32),
        (173, 32),
        (174, 32),
        (175, 32),
        (176, 32),
        (177, 32),
        (178, 32),
        (229, 32),
        (167, 32),
        (222, 32),
        (621, 32),
        (179, 33),
        (180, 33),
        (181, 33),
        (182, 33),
        (183, 33),
        (184, 33),
        (185, 33),
        (186, 33),
        (187, 33),
        (188, 33),
        (189, 33),
        (201, 35),
        (204, 35),
        (205, 35),
        (206, 35),
        (207, 35),
        (208, 35),
        (210, 35),
        (211, 35),
        (212, 35),
        (93, 35),
        (63, 35),
        (190, 49),
        (233, 49),
        (619, 49),
    ]

    mappings = [
        UserAssociation(user_id=users[mgr_id].id, association_id=assocs[assoc_id].id)
        for assoc_id, mgr_id in raw_mappings
    ]
    db.add_all(mappings)
    db.commit()

    print("")
    print("Done. Summary:")
    print(f"  {db.query(Association).count()} associations")
    print(f"  {db.query(User).filter(User.role == UserRole.manager).count()} managers")
    print(f"  {db.query(User).filter(User.role == UserRole.super_admin).count()} super admins")
    print(f"  {db.query(UserAssociation).count()} manager assignments")
    print("")
    print("Default credentials (password_change_required=True for all managers):")
    print("  super_admin  admin@cscmsi.com   $SEED_ADMIN_PASSWORD")
    print("  managers     <email>            $SEED_MANAGER_PASSWORD")
    db.close()


if __name__ == "__main__":
    seed()
