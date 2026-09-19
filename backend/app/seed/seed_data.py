"""
Seed the database with realistic synthetic data across all built modules so the full flow is
demonstrable end to end without any real personal data and without any live government API
(spec 2.6, "Seed data" / spec 3.1 deliverable #... "Seed data, demo script, README").

Run with: python -m app.seed.seed_data
"""

import io
import secrets
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models.jurisdiction import Ward
from app.models.module1_violations import (
    Challan,
    ChallanStatus,
    FineLadderConfig,
    IdentityPath,
    SyntheticVehicleRegistry,
    ViolationCase,
    ViolationCaseStatus,
    ViolationClassConfig,
)
from app.models.module2_corruption import (
    AccusedPartyType,
    CorruptionReport,
    ModerationStatus,
    PublicStatusBadge,
    RoutingRule,
)
from app.models.module4_emergency import EmergencyReportRoutingRule, OffenceCategory
from app.models.module3_infra import (
    InfrastructureIssue,
    IssueCategory,
    IssueStatus,
    IssueStatusHistory,
)
from app.models.officials import ResponsibleDesk
from app.models.users import User, UserRole
from app.services.sla import compute_sla_deadline
from app.services.storage import ensure_buckets, put_object

DEV_PASSWORD = "DevPassword123!"

# Fictional "Demo City" - four wards laid out as a 2x2 grid. Not a real place.
CITY_ORIGIN_LAT, CITY_ORIGIN_LNG = 12.9700, 77.5900
WARD_SIZE_DEG = 0.02

WARDS = [
    {"name": "Lakeview Ward", "ward_number": "12", "zone": "North Zone", "constituency": "Lakeview Assembly", "row": 0, "col": 0},
    {"name": "Market Ward", "ward_number": "13", "zone": "North Zone", "constituency": "Lakeview Assembly", "row": 0, "col": 1},
    {"name": "Riverside Ward", "ward_number": "27", "zone": "South Zone", "constituency": "Riverside Assembly", "row": 1, "col": 0},
    {"name": "Hillview Ward", "ward_number": "28", "zone": "South Zone", "constituency": "Riverside Assembly", "row": 1, "col": 1},
]

INFRA_CATEGORIES = [
    ("traffic_signal", "Non-functioning traffic signal", 24, "Traffic Police", "DCP Office"),
    ("water_leak", "Water leakage or burst pipeline", 24, "Water Board Zonal Engineer", None),
    ("fallen_tree", "Fallen tree blocking a road", 24, "Ward Officer", "Commissioner"),
    ("street_light", "Broken or dark street light", 72, "Electrical Department", "Ward Officer"),
    ("blocked_drain", "Blocked or overflowing drain", 72, "Sanitation", "Health Officer"),
    ("uncollected_garbage", "Uncollected garbage", 72, "Sanitation Inspector", None),
    ("pothole", "Pothole or damaged road", 24 * 7, "Roads Engineer", "MLA Office"),
    ("damaged_footpath", "Damaged footpath", 24 * 14, "Roads Engineer", None),
    ("broken_toilet", "Broken public toilet", 24 * 7, "Sanitation", "Health Officer"),
    ("damaged_bus_stop", "Damaged bus stop", 24 * 14, "Transport Corporation", None),
    ("illegal_hoarding", "Illegal hoarding", 24 * 7, "Town Planning", "Commissioner"),
    ("stray_cattle", "Stray cattle on roads", 48, "Animal Husbandry", "Ward Officer"),
]

VIOLATION_CLASSES = [
    ("littering", "Littering / throwing waste outside bins", IdentityPath.UNIDENTIFIED, "Municipal Solid Waste By-law s.12"),
    ("illegal_dumping", "Illegal dumping of construction/household waste", IdentityPath.ANPR, "Municipal Solid Waste By-law s.15"),
    ("spitting", "Spitting in public (gutka, paan, tobacco)", IdentityPath.UNIDENTIFIED, "Municipal By-law s.20"),
    ("public_urination", "Public urination or defecation", IdentityPath.UNIDENTIFIED, "Municipal By-law s.21"),
    ("vandalism", "Vandalism or damage to public property", IdentityPath.UNIDENTIFIED, "Prevention of Damage to Public Property Act"),
    ("illegal_posters", "Illegal posters, banners, wall defacement", IdentityPath.UNIDENTIFIED, "Municipal By-law s.25"),
    ("open_burning", "Open burning of garbage or leaves", IdentityPath.UNIDENTIFIED, "Air (Prevention & Control) Act"),
    ("footpath_encroachment", "Encroachment of footpaths by vendors/shops", IdentityPath.UNIDENTIFIED, "Municipal By-law s.30"),
    ("illegal_parking", "Parking on footpaths or in no-parking zones", IdentityPath.ANPR, "Motor Vehicles Act s.122"),
    ("waste_spilling_vehicle", "Vehicles dumping/spilling waste onto roads", IdentityPath.ANPR, "Motor Vehicles Act s.190"),
    ("tree_damage", "Unauthorised felling or damage to public trees", IdentityPath.UNIDENTIFIED, "Tree Preservation Act"),
]

ROUTING_RULES = [
    (AccusedPartyType.STATE_GOVT_EMPLOYEE, "State Lokayukta / Anti-Corruption Bureau", True),
    (AccusedPartyType.CENTRAL_GOVT_EMPLOYEE, "Central Vigilance Commission", True),
    (AccusedPartyType.POLICE_PERSONNEL, "State ACB and Police Complaints Authority", False),
    (AccusedPartyType.MUNICIPAL_OR_DEPT_STAFF, "District Vigilance Officer", True),
]

# Module 4 is not implemented, but its routing policy is seeded so the design - in particular
# the hard stop on any offence involving a minor - is reviewable in the database rather than
# living only in prose. (category, alert_routed_to, has_public_record, is_hard_stop)
EMERGENCY_ROUTING_RULES = [
    (OffenceCategory.ASSAULT_IN_PROGRESS, "112 control room and jurisdictional SHO", True, False),
    (OffenceCategory.HOMICIDE_OR_BODY_DISCOVERED, "112, jurisdictional SHO, district control room", True, False),
    (OffenceCategory.SEXUAL_OFFENCE_ADULT, "Women's Help Desk, SHO, nearest One Stop Centre", False, False),
    (OffenceCategory.MINOR_INVOLVED, "HARD STOP - refuse upload; redirect to 1098, 112, CCPWC portal", False, True),
    (OffenceCategory.NARCOTICS, "District anti-narcotics cell and SHO (not the beat officer)", True, False),
    (OffenceCategory.HUMAN_TRAFFICKING, "Anti Human Trafficking Unit and SHO", False, False),
]

USERS = [
    ("admin@demo.city", "Admin User", UserRole.ADMIN, None),
    ("officer.roads@demo.city", "R. Kumar (Municipal Officer)", UserRole.MUNICIPAL_OFFICER, None),
    ("engineer.sanitation@demo.city", "S. Iyer (Dept Engineer)", UserRole.DEPARTMENT_ENGINEER, None),
    ("moderator@demo.city", "M. Rao (Moderator)", UserRole.MODERATOR, None),
    ("vigilance@demo.city", "V. Nair (Vigilance Officer)", UserRole.VIGILANCE_OFFICER, None),
    ("investigator@demo.city", "I. Sharma (Investigating Officer)", UserRole.INVESTIGATING_OFFICER, None),
]


def _ward_polygon_wkt(row: int, col: int) -> str:
    lat0 = CITY_ORIGIN_LAT + row * WARD_SIZE_DEG
    lng0 = CITY_ORIGIN_LNG + col * WARD_SIZE_DEG
    lat1, lng1 = lat0 + WARD_SIZE_DEG, lng0 + WARD_SIZE_DEG
    return f"SRID=4326;POLYGON(({lng0} {lat0}, {lng1} {lat0}, {lng1} {lat1}, {lng0} {lat1}, {lng0} {lat0}))"


def _ward_center(row: int, col: int) -> tuple[float, float]:
    lat = CITY_ORIGIN_LAT + row * WARD_SIZE_DEG + WARD_SIZE_DEG / 2
    lng = CITY_ORIGIN_LNG + col * WARD_SIZE_DEG + WARD_SIZE_DEG / 2
    return lat, lng


def _placeholder_image_bytes(label: str, color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (640, 480), color=color)
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), f"SYNTHETIC SEED DATA\n{label}", fill=(255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def seed_wards(db: Session) -> dict[str, Ward]:
    wards = {}
    for w in WARDS:
        existing = db.execute(select(Ward).where(Ward.ward_number == w["ward_number"])).scalars().first()
        if existing:
            wards[w["name"]] = existing
            continue
        ward = Ward(
            name=w["name"],
            ward_number=w["ward_number"],
            municipal_zone=w["zone"],
            assembly_constituency=w["constituency"],
            city="Demo City",
            boundary=_ward_polygon_wkt(w["row"], w["col"]),
        )
        db.add(ward)
        wards[w["name"]] = ward
    db.commit()
    for w in WARDS:
        db.refresh(wards[w["name"]])
    return wards


def seed_desks(db: Session, wards: dict[str, Ward]) -> None:
    departments = [c[3] for c in INFRA_CATEGORIES] + [c[4] for c in INFRA_CATEGORIES if c[4]]
    departments = sorted(set(departments))
    if db.execute(select(ResponsibleDesk)).scalars().first():
        return
    for dept in departments:
        for w in WARDS:
            db.add(
                ResponsibleDesk(
                    department=dept,
                    designation=f"{dept} - {w['name']}",
                    ward_id=wards[w["name"]].id,
                    municipal_zone=w["zone"],
                    contact_name=f"Desk Officer, {dept}",
                    contact_email=f"{dept.lower().replace(' ', '.')}@{w['name'].lower().replace(' ', '')}.demo.city",
                    contact_phone="+91-90000-00000",
                )
            )
    db.commit()


def seed_infra_categories(db: Session) -> dict[str, IssueCategory]:
    categories = {}
    for slug, label, sla_hours, dept, dept2 in INFRA_CATEGORIES:
        existing = db.execute(select(IssueCategory).where(IssueCategory.slug == slug)).scalars().first()
        if existing:
            categories[slug] = existing
            continue
        cat = IssueCategory(
            slug=slug, label=label, sla_hours=sla_hours,
            escalation_department=dept, escalation_department_tier2=dept2,
            duplicate_radius_meters=50,
        )
        db.add(cat)
        categories[slug] = cat
    db.commit()
    for slug in categories:
        db.refresh(categories[slug])
    return categories


def seed_violation_classes(db: Session) -> dict[str, ViolationClassConfig]:
    classes = {}
    for slug, label, identity_path, section in VIOLATION_CLASSES:
        existing = db.execute(select(ViolationClassConfig).where(ViolationClassConfig.slug == slug)).scalars().first()
        if existing:
            classes[slug] = existing
            continue
        vc = ViolationClassConfig(slug=slug, label=label, identity_path=identity_path, statutory_section=section)
        db.add(vc)
        classes[slug] = vc
    db.commit()
    for slug in classes:
        db.refresh(classes[slug])

    if not db.execute(select(FineLadderConfig)).scalars().first():
        for vc in classes.values():
            db.add(FineLadderConfig(violation_class_id=vc.id, occurrence_number=1, amount_rupees=500))
            db.add(FineLadderConfig(violation_class_id=vc.id, occurrence_number=2, amount_rupees=1000))
    db.commit()
    return classes


def seed_vehicle_registry(db: Session) -> list[SyntheticVehicleRegistry]:
    if db.execute(select(SyntheticVehicleRegistry)).scalars().first():
        return db.execute(select(SyntheticVehicleRegistry)).scalars().all()
    plates = [
        ("KA01AB1234", "Fictional Owner A", "+91-90000-11111"),
        ("KA05CD5678", "Fictional Owner B", "+91-90000-22222"),
        ("KA09EF9012", "Fictional Owner C", "+91-90000-33333"),
    ]
    rows = []
    for plate, owner, phone in plates:
        row = SyntheticVehicleRegistry(plate_number=plate, owner_name=owner, contact_phone=phone)
        db.add(row)
        rows.append(row)
    db.commit()
    return rows


def seed_routing_rules(db: Session) -> None:
    if db.execute(select(RoutingRule)).scalars().first():
        return
    for accused_type, body, notify_police in ROUTING_RULES:
        db.add(RoutingRule(accused_party_type=accused_type, primary_route_body=body, notify_local_police=notify_police))
    db.commit()


def seed_emergency_routing_rules(db: Session) -> None:
    if db.execute(select(EmergencyReportRoutingRule)).scalars().first():
        return
    for category, routed_to, public_record, hard_stop in EMERGENCY_ROUTING_RULES:
        db.add(
            EmergencyReportRoutingRule(
                category=category,
                alert_routed_to=routed_to,
                has_public_record=public_record,
                is_hard_stop=hard_stop,
            )
        )
    db.commit()


def seed_users(db: Session, wards: dict[str, Ward]) -> dict[str, User]:
    users = {}
    ward_ids = list(wards.values())
    for i, (email, name, role, dept) in enumerate(USERS):
        existing = db.execute(select(User).where(User.email == email)).scalars().first()
        if existing:
            users[email] = existing
            continue
        user = User(
            email=email,
            full_name=name,
            hashed_password=hash_password(DEV_PASSWORD),
            role=role,
            jurisdiction_ward_id=ward_ids[i % len(ward_ids)].id if role != UserRole.ADMIN else None,
        )
        db.add(user)
        users[email] = user
    db.commit()
    for email in users:
        db.refresh(users[email])
    return users


def seed_sample_infra_issues(db: Session, wards: dict[str, Ward], categories: dict[str, IssueCategory]) -> None:
    if db.execute(select(InfrastructureIssue)).scalars().first():
        return
    ensure_buckets()

    samples = [
        ("pothole", "Lakeview Ward", IssueStatus.REPORTED, (255, 140, 0)),
        ("street_light", "Market Ward", IssueStatus.ACKNOWLEDGED, (30, 30, 30)),
        ("uncollected_garbage", "Riverside Ward", IssueStatus.OVERDUE, (100, 80, 40)),
        ("blocked_drain", "Hillview Ward", IssueStatus.RESOLVED, (60, 90, 160)),
        ("pothole", "Market Ward", IssueStatus.REPORTED, (255, 140, 0)),
    ]

    for slug, ward_name, target_status, color in samples:
        ward = wards[ward_name]
        row = next(w for w in WARDS if w["name"] == ward_name)
        lat, lng = _ward_center(row["row"], row["col"])
        category = categories[slug]

        media_id = put_object(_placeholder_image_bytes(f"{category.label} - {ward_name}", color), "image/jpeg", key_prefix="module3")

        if target_status == IssueStatus.OVERDUE:
            sla_deadline = datetime.now(timezone.utc) - timedelta(hours=5)
        else:
            sla_deadline = compute_sla_deadline(category.sla_hours)

        issue = InfrastructureIssue(
            category_id=category.id,
            description=f"Synthetic seed report: {category.label} near {ward_name} center.",
            location=f"SRID=4326;POINT({lng} {lat})",
            ward_id=ward.id,
            media_id=media_id,
            tracking_token=secrets.token_urlsafe(24),
            sla_deadline=sla_deadline,
            status=target_status,
        )
        if target_status == IssueStatus.RESOLVED:
            issue.resolved_at = datetime.now(timezone.utc)
            issue.resolution_proof_media_id = put_object(
                _placeholder_image_bytes(f"RESOLVED - {category.label}", (0, 150, 0)), "image/jpeg", key_prefix="module3/resolution_proof"
            )
        db.add(issue)
        db.flush()
        db.add(IssueStatusHistory(issue_id=issue.id, status=IssueStatus.REPORTED, note="Report received (seed data)"))
        if target_status != IssueStatus.REPORTED:
            db.add(IssueStatusHistory(issue_id=issue.id, status=target_status, note="Seed data"))

    db.commit()


def seed_sample_violation_cases(db: Session, wards: dict[str, Ward], classes: dict[str, ViolationClassConfig], vehicles: list[SyntheticVehicleRegistry]) -> None:
    if db.execute(select(ViolationCase)).scalars().first():
        return
    ensure_buckets()

    lat, lng = _ward_center(0, 0)
    media_id = put_object(_placeholder_image_bytes("Illegal parking - camera 3", (50, 50, 90)), "image/jpeg", key_prefix="module1")
    db.add(
        ViolationCase(
            violation_class_id=classes["illegal_parking"].id,
            confidence_score=0.91,
            camera_id="CAM-003",
            location=f"SRID=4326;POINT({lng} {lat})",
            media_id=media_id,
            identity_path=IdentityPath.ANPR,
            resolved_plate_number=vehicles[0].plate_number,
            status=ViolationCaseStatus.PENDING_REVIEW,
        )
    )

    lat2, lng2 = _ward_center(1, 0)
    media_id2 = put_object(_placeholder_image_bytes("Littering - camera 7", (90, 60, 30)), "image/jpeg", key_prefix="module1")
    db.add(
        ViolationCase(
            violation_class_id=classes["littering"].id,
            confidence_score=0.83,
            camera_id="CAM-007",
            location=f"SRID=4326;POINT({lng2} {lat2})",
            media_id=media_id2,
            identity_path=IdentityPath.UNIDENTIFIED,
            status=ViolationCaseStatus.PENDING_REVIEW,
        )
    )
    db.commit()


def seed_sample_corruption_reports(db: Session) -> None:
    if db.execute(select(CorruptionReport)).scalars().first():
        return
    ensure_buckets()

    media_id = put_object(_placeholder_image_bytes("Corruption report (seed, pending)", (80, 20, 20)), "image/jpeg", key_prefix="module2")
    db.add(
        CorruptionReport(
            accused_department="Municipal Licensing Office",
            accused_designation="Licensing Inspector",
            accused_party_type=AccusedPartyType.MUNICIPAL_OR_DEPT_STAFF,
            description="Synthetic seed report awaiting moderation.",
            geohash="tdr1x",
            media_id=media_id,
            tracking_token=secrets.token_urlsafe(24),
            moderation_status=ModerationStatus.PENDING,
        )
    )

    media_id2 = put_object(_placeholder_image_bytes("Corruption report (seed, published)", (20, 60, 20)), "image/jpeg", key_prefix="module2")
    db.add(
        CorruptionReport(
            accused_department="Roads & Works Department",
            accused_designation="Contract Supervisor",
            accused_party_type=AccusedPartyType.MUNICIPAL_OR_DEPT_STAFF,
            description="Synthetic seed report already moderated and published.",
            geohash="tdr1y",
            media_id=media_id2,
            tracking_token=secrets.token_urlsafe(24),
            moderation_status=ModerationStatus.APPROVED,
            public_status_badge=PublicStatusBadge.UNDER_INVESTIGATION,
        )
    )
    db.commit()


def main() -> None:
    Base.metadata.create_all(bind=engine)  # safety net; alembic upgrade head is the real source of truth
    db = SessionLocal()
    try:
        ensure_buckets()
        wards = seed_wards(db)
        seed_desks(db, wards)
        categories = seed_infra_categories(db)
        classes = seed_violation_classes(db)
        vehicles = seed_vehicle_registry(db)
        seed_routing_rules(db)
        seed_emergency_routing_rules(db)
        seed_users(db, wards)
        seed_sample_infra_issues(db, wards, categories)
        seed_sample_violation_cases(db, wards, classes, vehicles)
        seed_sample_corruption_reports(db)
        print("Seed complete.")
        print(f"\nDemo official accounts (password: {DEV_PASSWORD}):")
        for email, _, role, _ in USERS:
            print(f"  {email}  [{role.value}]")

        # A tracking token is tied to no identity, so there is no way to look one up by anything
        # else. Printing the seeded ones is the only way to demo the citizen tracking page
        # without first submitting a fresh report.
        print("\nTracking codes for the seeded reports (paste into 'Track a report'):")
        seeded = db.execute(
            select(InfrastructureIssue, IssueCategory)
            .join(IssueCategory, IssueCategory.id == InfrastructureIssue.category_id)
            .order_by(InfrastructureIssue.created_at)
        ).all()
        for issue, category in seeded:
            print(f"  {issue.tracking_token}  {issue.status.value:<12} {category.label}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
