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
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import get_settings
from app.database import Base, SessionLocal, engine, geo_point
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
from app.models.module2_grievance import (
    Grievance,
    GrievanceGround,
    GrievanceStatus,
    ReplyStatus,
    RightOfReply,
)
from app.models.module2_corruption import (
    AccusedPartyType,
    CorruptionReport,
    ModerationStatus,
    PublicStatusBadge,
    RoutingRule,
)
from app.models.module4_emergency import (
    ChainOfCustodyEntry,
    EmergencyReport,
    EmergencyReportRoutingRule,
    OffenceCategory,
    PoliceStation,
)
from app.services.evidence_vault import seal, store_evidence
from app.models.module3_infra import (
    InfrastructureIssue,
    IssueCategory,
    IssueStatus,
    IssueStatusHistory,
)
from app.models.officials import ResponsibleDesk
from app.models.station import CaseDiaryEntry, DiaryEntryType, FirRecord, FirStatus
from app.models.users import User, UserRole
from app.services.grievance import new_ticket
from app.services.sla import compute_sla_deadline
from app.services.station import investigation_deadline, log_diary, next_fir_number
from app.services.tracking import new_tracking_code
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

# code, name, ward, lat offset, lng offset, SHO, address
STATIONS = [
    ("PS-01", "Lakeview Police Station", "Lakeview Ward", 0.002, -0.003, "Insp. A. Menon", "1 Lake Road, Lakeview"),
    ("PS-02", "Market Police Station", "Market Ward", -0.001, 0.002, "Insp. B. Das", "12 Bazaar Street, Market"),
    ("PS-03", "Riverside Police Station", "Riverside Ward", 0.003, 0.001, "Insp. C. Pillai", "44 River Road, Riverside"),
    ("PS-04", "Hillview Police Station", "Hillview Ward", -0.002, -0.002, "Insp. D. Reddy", "7 Hill Road, Hillview"),
    # Second stations in the two busier wards.
    ("PS-05", "Market East Police Station", "Market Ward", 0.006, 0.006, "Insp. E. Fernandes", "90 East Market Road"),
    ("PS-06", "Riverside Industrial Police Station", "Riverside Ward", -0.006, 0.005, "Insp. F. Khan", "3 Mill Lane, Riverside"),
]

# (email, name, role, ward for non-police scoping, station code for police roles)
USERS = [
    ("admin@demo.city", "Admin User", UserRole.ADMIN, None, None),
    ("officer.roads@demo.city", "R. Kumar (Municipal Officer)", UserRole.MUNICIPAL_OFFICER, None, None),
    ("engineer.sanitation@demo.city", "S. Iyer (Dept Engineer)", UserRole.DEPARTMENT_ENGINEER, None, None),
    ("moderator@demo.city", "M. Rao (Moderator)", UserRole.MODERATOR, None, None),
    ("vigilance@demo.city", "V. Nair (Vigilance Officer)", UserRole.VIGILANCE_OFFICER, None, None),
    # Riverside holds the seeded report with sealed evidence, so this account demonstrates the
    # jurisdiction-scoped evidence flow as well as the station procedures.
    ("investigator@demo.city", "I. Sharma (SI, Riverside)", UserRole.INVESTIGATING_OFFICER, "Riverside Ward", "PS-03"),
    ("sho.lakeview@demo.city", "A. Menon (Inspector, Lakeview)", UserRole.INVESTIGATING_OFFICER, "Lakeview Ward", "PS-01"),
    ("sho.market@demo.city", "B. Das (Inspector, Market)", UserRole.INVESTIGATING_OFFICER, "Market Ward", "PS-02"),
    ("io.riverside@demo.city", "P. Ganesh (SI, Riverside)", UserRole.INVESTIGATING_OFFICER, "Riverside Ward", "PS-03"),
]


def _ward_polygon_wkt(row: int, col: int) -> str:
    lat0 = CITY_ORIGIN_LAT + row * WARD_SIZE_DEG
    lng0 = CITY_ORIGIN_LNG + col * WARD_SIZE_DEG
    lat1, lng1 = lat0 + WARD_SIZE_DEG, lng0 + WARD_SIZE_DEG
    # Latitude first: MySQL reads SRID 4326 in EPSG axis order. A ring must also close on
    # its first vertex or MySQL rejects the polygon outright.
    return (
        f"POLYGON(({lat0} {lng0}, {lat0} {lng1}, {lat1} {lng1}, {lat1} {lng0}, {lat0} {lng0}))"
    )


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


def seed_police_stations(db: Session, wards: dict[str, Ward]) -> dict[str, PoliceStation]:
    """
    Six stations across four wards - two wards hold two each, which is why reports route to the
    nearest station rather than assuming one ward means one station.
    """
    stations: dict[str, PoliceStation] = {}
    for code, name, ward_name, dlat, dlng, sho, address in STATIONS:
        existing = db.execute(select(PoliceStation).where(PoliceStation.code == code)).scalars().first()
        if existing:
            stations[code] = existing
            continue
        row = next(w for w in WARDS if w["name"] == ward_name)
        lat, lng = _ward_center(row["row"], row["col"])
        station = PoliceStation(
            name=name,
            code=code,
            ward_id=wards[ward_name].id,
            address=address,
            location=geo_point(lat + dlat, lng + dlng),
            sho_name=sho,
            contact_phone="+91-90000-10000",
            contact_email=f"{code.lower()}@police.demo.city",
        )
        db.add(station)
        stations[code] = station
    db.commit()
    for code in stations:
        db.refresh(stations[code])
    return stations


def seed_emergency_reports(db: Session, wards: dict[str, Ward], stations: dict[str, PoliceStation]) -> None:
    """
    Shapes the data so both the station section and the public ledger demonstrate something:
    one station sitting on unacknowledged reports past the FIR deadline (flagged red), one
    working its cases through FIR, case diary and chargesheet, a Zero FIR registered at the
    wrong station and transferred, a past-quarter cluster above the k-anonymity threshold and
    one below it, and a restricted report that appears on no public surface at all.
    """
    if db.execute(select(EmergencyReport)).scalars().first():
        return
    ensure_buckets()
    now = datetime.now(timezone.utc)
    last_quarter = now - timedelta(days=100)

    ward_station = {
        "Lakeview Ward": "PS-01",
        "Market Ward": "PS-02",
        "Riverside Ward": "PS-03",
        "Hillview Ward": "PS-04",
    }

    def add(category, ward_name, created, *, station_code=None, acknowledged=None, closed_reason=None, restricted=False):
        station = stations[station_code or ward_station[ward_name]]
        report = EmergencyReport(
            category=category,
            geohash="tdr1x",
            ward_id=wards[ward_name].id,
            station_id=station.id,
            tracking_token=secrets.token_urlsafe(24),
            is_restricted=restricted,
            created_at=created,
            acknowledged_at=acknowledged,
            closed_without_fir_reason=closed_reason,
            closed_at=created + timedelta(days=2) if closed_reason else None,
        )
        db.add(report)
        db.flush()
        log_diary(
            db,
            station_id=station.id,
            entry_type=DiaryEntryType.COMPLAINT_RECEIVED,
            detail=f"Report received ({category.value}), ward {ward_name}",
            report_id=report.id,
        )
        return report, station

    def register_fir(report, station, sections, officer, when, *, is_zero_fir=False, status=FirStatus.UNDER_INVESTIGATION):
        number, year = next_fir_number(db, station.id, when.year)
        fir = FirRecord(
            station_id=station.id,
            fir_number=number,
            year=year,
            report_id=report.id,
            sections=sections,
            is_zero_fir=is_zero_fir,
            registered_by_user_id=officer.id,
            registered_at=when,
            investigating_officer_id=officer.id,
            investigation_deadline=investigation_deadline(report.category, when),
            status=status,
        )
        db.add(fir)
        db.flush()
        log_diary(
            db,
            station_id=station.id,
            entry_type=DiaryEntryType.FIR_REGISTERED,
            detail=f"FIR {number} registered u/s {sections}" + (" - ZERO FIR" if is_zero_fir else ""),
            officer_user_id=officer.id,
            report_id=report.id,
            fir_id=fir.id,
        )
        return fir

    market_officer = db.execute(
        select(User).where(User.email == "sho.market@demo.city")
    ).scalars().first()
    riverside_officer = db.execute(
        select(User).where(User.email == "investigator@demo.city")
    ).scalars().first()

    # Lakeview: sitting on reports. Two are past the 7-day FIR deadline, so it flags red.
    for days in (9, 8, 3):
        add(OffenceCategory.ASSAULT_IN_PROGRESS, "Lakeview Ward", now - timedelta(days=days))

    # Market: acknowledging quickly, registering FIRs, one carried through to chargesheet.
    for i, days in enumerate((6, 4, 2)):
        created = now - timedelta(days=days)
        report, station = add(
            OffenceCategory.HOMICIDE_OR_BODY_DISCOVERED if i == 0 else OffenceCategory.ASSAULT_IN_PROGRESS,
            "Market Ward",
            created,
            acknowledged=created + timedelta(hours=1),
        )
        fir = register_fir(
            report,
            station,
            "BNS 103" if i == 0 else "BNS 115(2)",
            market_officer,
            created + timedelta(hours=6),
            status=FirStatus.CHARGESHEET_FILED if i == 0 else FirStatus.UNDER_INVESTIGATION,
        )
        if i == 0:
            fir.chargesheet_filed_at = created + timedelta(days=1)
            fir.court_name = "Chief Judicial Magistrate, Demo City"
            log_diary(
                db,
                station_id=station.id,
                entry_type=DiaryEntryType.CHARGESHEET_FILED,
                detail=f"FIR {fir.fir_number}: chargesheet filed before {fir.court_name}",
                officer_user_id=market_officer.id,
                fir_id=fir.id,
            )
        for note in ("Scene visited, witnesses recorded.", "CCTV from the adjoining shop requisitioned."):
            db.add(CaseDiaryEntry(fir_id=fir.id, officer_user_id=market_officer.id, detail=note))

    closed = now - timedelta(days=5)
    add(
        OffenceCategory.ASSAULT_IN_PROGRESS,
        "Market Ward",
        closed,
        acknowledged=closed + timedelta(hours=2),
        closed_reason="Complainant withdrew; no cognizable offence made out",
    )

    # A Zero FIR: reported at Market East, the offence falls under Market, so it is registered
    # here and the investigation transferred rather than the complainant being turned away.
    zero_created = now - timedelta(days=3)
    zero_report, zero_station = add(
        OffenceCategory.ASSAULT_IN_PROGRESS,
        "Market Ward",
        zero_created,
        station_code="PS-05",
        acknowledged=zero_created + timedelta(minutes=30),
    )
    zero_fir = register_fir(
        zero_report, zero_station, "BNS 115(2)", market_officer, zero_created + timedelta(hours=1), is_zero_fir=True
    )
    zero_fir.transferred_to_station_id = stations["PS-02"].id
    zero_fir.status = FirStatus.TRANSFERRED
    zero_report.station_id = stations["PS-02"].id
    log_diary(
        db,
        station_id=zero_station.id,
        entry_type=DiaryEntryType.ZERO_FIR_TRANSFERRED_OUT,
        detail=f"FIR {zero_fir.fir_number} transferred to Market Police Station: offence within their jurisdiction",
        officer_user_id=market_officer.id,
        fir_id=zero_fir.id,
        report_id=zero_report.id,
    )
    log_diary(
        db,
        station_id=stations["PS-02"].id,
        entry_type=DiaryEntryType.TRANSFERRED_IN,
        detail=f"FIR {zero_fir.fir_number} received from Market East Police Station",
        fir_id=zero_fir.id,
        report_id=zero_report.id,
    )

    # Riverside: a past-quarter narcotics cluster, above the k-anonymity threshold of five.
    for i in range(6):
        created = last_quarter - timedelta(days=i)
        report, station = add(
            OffenceCategory.NARCOTICS,
            "Riverside Ward",
            created,
            acknowledged=created + timedelta(hours=3),
        )
        if i < 2:
            register_fir(report, station, "NDPS 21(b)", riverside_officer, created + timedelta(hours=5))

    # Hillview: only three in the same past quarter, so the map must suppress the cell.
    for i in range(3):
        add(OffenceCategory.ASSAULT_IN_PROGRESS, "Hillview Ward", last_quarter - timedelta(days=i))

    # Restricted: never on the ledger, the hotspot map, or any other public surface.
    add(
        OffenceCategory.SEXUAL_OFFENCE_ADULT,
        "Market Ward",
        now - timedelta(days=4),
        acknowledged=now - timedelta(days=4) + timedelta(hours=1),
        restricted=True,
    )

    # One report holding sealed evidence, so the investigating-officer flow is demonstrable.
    with_evidence, _ = add(
        OffenceCategory.NARCOTICS,
        "Riverside Ward",
        now - timedelta(days=1),
        acknowledged=now - timedelta(hours=20),
    )
    evidence = _placeholder_image_bytes("SEALED EVIDENCE - synthetic", (30, 30, 60))
    with_evidence.original_sha256 = seal(evidence)
    with_evidence.media_id = store_evidence(evidence, "image/jpeg")
    db.flush()
    db.add(
        ChainOfCustodyEntry(
            report_id=with_evidence.id,
            action="sealed",
            detail=f"sha256={with_evidence.original_sha256}",
        )
    )

    db.commit()


def seed_users(db: Session, wards: dict[str, Ward], stations: dict[str, PoliceStation]) -> dict[str, User]:
    users = {}
    ward_ids = list(wards.values())
    for i, (email, name, role, dept, station_code) in enumerate(USERS):
        existing = db.execute(select(User).where(User.email == email)).scalars().first()
        if existing:
            users[email] = existing
            continue
        if role == UserRole.ADMIN:
            assigned_ward = None
        elif dept and dept in wards:
            assigned_ward = wards[dept].id
        else:
            assigned_ward = ward_ids[i % len(ward_ids)].id
        user = User(
            email=email,
            full_name=name,
            hashed_password=hash_password(DEV_PASSWORD),
            role=role,
            jurisdiction_ward_id=assigned_ward,
            police_station_id=stations[station_code].id if station_code else None,
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
            location=geo_point(lat, lng),
            ward_id=ward.id,
            media_id=media_id,
            tracking_token=new_tracking_code(db),
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
            location=geo_point(lat, lng),
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
            location=geo_point(lat2, lng2),
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


def seed_grievance_demo(db: Session) -> None:
    """
    One published reply and one open grievance against the seeded published report.

    Without these the grievance queue and the reply block under a feed card are both empty on a
    fresh database, and the two features that answer "what happens when the platform gets it
    wrong" are invisible in a demo.
    """
    if db.execute(select(RightOfReply)).scalars().first():
        return

    report = db.execute(
        select(CorruptionReport).where(
            CorruptionReport.moderation_status == ModerationStatus.APPROVED,
            CorruptionReport.taken_down_at.is_(None),
        )
    ).scalars().first()
    if report is None:
        return

    db.add(
        RightOfReply(
            report_id=report.id,
            body=(
                "The Department has referred this to its Vigilance Cell. The tender in question "
                "was awarded under open bidding, reference RWD/2026/114, and the file is with the "
                "internal auditor. We will publish the audit finding when it is received."
            ),
            author_department=report.accused_department,
            author_designation="Executive Engineer",
            author_name="Synthetic Seed Official",
            author_contact_email="ee@roads-works.example.gov.in",
            status=ReplyStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
        )
    )

    db.add(
        Grievance(
            ticket=new_ticket(db),
            report_id=report.id,
            ground=GrievanceGround.FACTUALLY_INCORRECT,
            body=(
                "The report states the work was never carried out. Completion certificate "
                "RWD/CC/2026/88 was issued on site and is available on request. We ask that the "
                "report be corrected or withdrawn."
            ),
            complainant_name="Synthetic Seed Complainant",
            complainant_email="grievance-demo@example.gov.in",
            complainant_designation="Executive Engineer",
            status=GrievanceStatus.ACKNOWLEDGED,
            acknowledged_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def main() -> None:
    # These accounts share a password that is printed below and documented in the README. Seeding
    # a real environment would hand anyone who read either an officer login.
    if not get_settings().is_development:
        raise SystemExit(
            f"Refusing to seed demo accounts with ENV={get_settings().env}. "
            "Seed data is for local development only."
        )

    # Deliberately does NOT create tables. create_all() builds the schema without the things only
    # migrations add - the append-only triggers on the audit log, chain of custody and station
    # diaries, and the one that stops a restricted report being unrestricted - so a failed
    # migration would be papered over with a database that merely looks right. On MySQL it could
    # not succeed anyway: this script connects as the application account, which holds no DDL.
    try:
        with engine.connect() as connection:
            stamped = connection.execute(text("SELECT count(*) FROM alembic_version")).scalar()
    except OperationalError as exc:
        # Almost always the hardening step: until it runs, the application account has no
        # privileges at all and even reading alembic_version is refused. Say so, rather than
        # letting a raw "access denied" send someone hunting for a wrong password.
        raise SystemExit(
            f"Could not read the database as the application account: {exc.orig}\n"
            "If this is access denied, the privileges have not been applied yet. Run:\n"
            "  alembic upgrade head && python -m app.db.harden"
        ) from exc
    if not stamped:
        raise SystemExit("Database is not migrated. Run: alembic upgrade head")
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
        stations = seed_police_stations(db, wards)
        seed_users(db, wards, stations)
        seed_emergency_reports(db, wards, stations)
        seed_sample_infra_issues(db, wards, categories)
        seed_sample_violation_cases(db, wards, classes, vehicles)
        seed_sample_corruption_reports(db)
        seed_grievance_demo(db)
        print("Seed complete.")
        print(f"\nDemo official accounts (password: {DEV_PASSWORD}):")
        for email, _, role, _, station_code in USERS:
            print(f"  {email}  [{role.value}]" + (f" @ {station_code}" if station_code else ""))

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
