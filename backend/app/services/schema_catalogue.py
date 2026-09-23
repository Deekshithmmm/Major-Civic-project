"""
Plain-English names and explanations for every table, for the database view at /database.

This file exists because a schema browser is not a database explanation. `fir_records`,
`ZERO_FIR_TRANSFERRED_OUT` and a column of 32-character identifiers are readable to someone who
already knows the system, which is the one person who does not need to look. Everything here is
hand-written for someone who does not.

Two rules held throughout:

  - **Say what a row *is*, not what the table stores.** "One complaint about a pothole" beats
    "civic infrastructure issue records".
  - **Never widen access.** Some columns are masked below and the reader is told which and why.
    A page built to make the database understandable must not become the one place where every
    access control in the system is bypassed.
"""

# Ordered: the groups appear on the page in this sequence.
GROUPS = [
    ("city", "The city itself", "Wards, departments, police stations and staff accounts. Everything else points back to these."),
    ("infra", "Roads, water and waste", "Potholes, broken street lights, uncollected rubbish - reported by residents, fixed by the council."),
    ("corruption", "Corruption reports", "Anonymous reports of bribery, and the right of the office concerned to answer them."),
    ("violations", "Traffic and violations", "Violations caught on camera or reported, and the fines an officer chose to issue."),
    ("emergency", "Emergencies and police work", "Serious incidents, the evidence attached to them, and the station's own paperwork."),
    ("record", "The permanent record", "What was done, by whom, and when. Nothing in here can ever be changed or removed."),
]

# label      - what to call the table on screen
# row_is     - what a single row represents, in one line
# purpose    - a sentence or two of context
# masked     - {column: reason} withheld from the row preview
# note       - an extra caution or point of interest shown alongside the table
TABLES = {
    # ---------------------------------------------------------------- city --
    "wards": {
        "group": "city", "label": "Wards",
        "row_is": "One ward of the city.",
        "purpose": "The map the whole system routes on. Each ward is stored as a real map shape, not just a name, so a dropped pin can be matched to the ward that contains it.",
    },
    "responsible_desks": {
        "group": "city", "label": "Who is responsible",
        "row_is": "One department's desk in one ward.",
        "purpose": "Answers 'who should fix this?'. A pothole in Lakeview goes to the Roads desk for Lakeview, and this table is where that lookup happens.",
    },
    "police_stations": {
        "group": "city", "label": "Police stations",
        "row_is": "One police station.",
        "purpose": "The station network, with each station's location on the map. A ward can hold more than one station, so an incident is routed to the nearest one rather than to the ward's.",
    },
    "users": {
        "group": "city", "label": "Staff accounts",
        "row_is": "One official's login.",
        "purpose": "Officials only. Residents never have an account anywhere in this system - that is the point of it, and it is why this table is small.",
        "masked": {"hashed_password": "A password, even scrambled, is never shown."},
    },
    # --------------------------------------------------------------- infra --
    "issue_categories": {
        "group": "infra", "label": "Types of problem",
        "row_is": "One kind of problem a resident can report.",
        "purpose": "Potholes, broken lights, blocked drains. Each carries its own deadline and the distance within which two reports count as the same problem - both set here rather than written into the code.",
    },
    "infrastructure_issues": {
        "group": "infra", "label": "Reported problems",
        "row_is": "One problem someone reported.",
        "purpose": "The main table for everyday civic complaints. Each has a tracking code the resident can use to follow it without an account.",
    },
    "issue_status_history": {
        "group": "infra", "label": "What happened next",
        "row_is": "One step in a problem's life.",
        "purpose": "Reported, seen, being fixed, fixed. This is what the public timeline on a report is built from, so progress cannot be quietly rewritten.",
    },
    "issue_contact_phones": {
        "group": "infra", "label": "Update numbers",
        "row_is": "One phone number, for updates only.",
        "purpose": "Optional. Kept in its own table, deliberately apart from the report, and deleted once the problem is fixed.",
        "masked": {"phone_number": "A resident's phone number. Kept apart from their report on purpose - showing it here would undo that."},
        "note": "The separation is the feature. Nothing joins this table to a report in a way that would reveal who filed it.",
    },
    # ----------------------------------------------------------- corruption --
    "corruption_reports": {
        "group": "corruption", "label": "Corruption reports",
        "row_is": "One anonymous report of corruption.",
        "purpose": "Filed with no account, no phone number and no email. Look at the columns: there is no 'who sent this' column at all, because none was ever created.",
        "masked": {
            "media_id": "The evidence file. Reachable only through the app's own checks, never by browsing.",
            "tracking_token": "The reporter's only handle on their report. Anyone holding it can read that report's status.",
        },
        "note": "The absence is the design. No IP address, no account, no device identifier - there is nothing to hand over because nothing was collected.",
    },
    "corruption_routing_rules": {
        "group": "corruption", "label": "Where reports are sent",
        "row_is": "One rule for one kind of accused official.",
        "purpose": "Decides which watchdog body receives a report. The rule that matters most: a report about police is never sent to the local police.",
    },
    "content_grievances": {
        "group": "corruption", "label": "Objections to a report",
        "row_is": "One complaint that a published report is wrong.",
        "purpose": "If something published here is wrong about you, this is the trail of your complaint and what was decided. The law gives 24 hours to acknowledge it and 15 days to decide.",
        "masked": {"complainant_email": "The complainant is a named person who wrote to us in confidence."},
    },
    "right_of_reply": {
        "group": "corruption", "label": "Replies from the office",
        "row_is": "One response from the department an allegation was about.",
        "purpose": "Published underneath the allegation, so a reader sees both sides in the same place.",
        "masked": {"author_contact_email": "Collected only to check the reply is genuine, and never published."},
    },
    # ----------------------------------------------------------- violations --
    "violation_class_configs": {
        "group": "violations", "label": "Types of violation",
        "row_is": "One kind of violation.",
        "purpose": "Wrong-side driving, illegal parking, littering. Configurable per city rather than fixed in the code.",
    },
    "fine_ladder_configs": {
        "group": "violations", "label": "Fine amounts",
        "row_is": "The fine for one violation at one offence number.",
        "purpose": "First offence, second, third. Read from this table every time, so nobody can quietly invent a figure.",
    },
    "violation_cases": {
        "group": "violations", "label": "Violation cases",
        "row_is": "One violation waiting for an officer to decide.",
        "purpose": "Nothing here becomes a fine on its own. Every case sits until a named officer looks at the evidence and confirms it.",
    },
    "challans": {
        "group": "violations", "label": "Fines issued",
        "row_is": "One fine, issued by a named officer.",
        "purpose": "The record of a decision a person made. A fine issued automatically by software would have no legal standing, so the system never issues one.",
    },
    "synthetic_vehicle_registry": {
        "group": "violations", "label": "Demo vehicle list",
        "row_is": "One made-up vehicle.",
        "purpose": "Invented plates for the demonstration. No real vehicle database is contacted anywhere in this system.",
    },
    # ------------------------------------------------------------ emergency --
    "emergency_reports": {
        "group": "emergency", "label": "Emergency reports",
        "row_is": "One report of a serious incident.",
        "purpose": "Assaults, accidents, crimes in progress. These are routed straight to a police station and never appear on any public feed.",
        "masked": {
            "media_id": "Evidence of a serious crime. Reachable only by an investigating officer quoting a case number.",
            "tracking_token": "The reporter's only handle on their report.",
            "geohash": "Roughly where it happened. Withheld while a case may still be open.",
        },
        "note": "Anything involving a child is refused before it is ever written down, so no such row exists here to find.",
    },
    "emergency_routing_rules": {
        "group": "emergency", "label": "How emergencies are handled",
        "row_is": "One rule for one kind of offence.",
        "purpose": "Sets what happens for each kind of incident: who is told, how fast, and whether the evidence is sealed.",
    },
    "chain_of_custody_entries": {
        "group": "emergency", "label": "Evidence handling log",
        "row_is": "One time evidence was sealed or opened.",
        "purpose": "Every seal and every access, with the case number it was opened under. This is what lets evidence stand up later.",
        "masked": {"case_number": "An open investigation's case number."},
    },
    "station_diary_entries": {
        "group": "emergency", "label": "Station daily diary",
        "row_is": "One numbered line in a station's daily diary.",
        "purpose": "The General Diary that every Indian police station keeps by law, numbered per station per day. The paperwork is the point: a station's public record only means something if it matches the register it actually keeps.",
    },
    "fir_records": {
        "group": "emergency", "label": "FIR register",
        "row_is": "One First Information Report.",
        "purpose": "An FIR is the formal start of a criminal case. The number is issued by the station itself, in its own sequence, exactly as on paper.",
    },
    "case_diary_entries": {
        "group": "emergency", "label": "Investigation diary",
        "row_is": "One day's note by the investigating officer.",
        "purpose": "The running record of an investigation, required by law. Notes can be added but never edited or removed.",
    },
    # --------------------------------------------------------------- record --
    "audit_log": {
        "group": "record", "label": "The permanent record",
        "row_is": "One thing an official did.",
        "purpose": "Every view, confirmation, fine and removal, with who did it and when. The database physically refuses to change or delete a row here - try it and see.",
        "note": "This is the table the whole system leans on. If it could be edited, nothing else here would be worth trusting.",
    },
}

# Columns whose name does not say what they are. Everything else is titled from its own name.
COLUMN_NOTES = {
    "wards.boundary": "The ward's shape on the map.",
    "issue_categories.sla_hours": "How long the council has before this is late.",
    "issue_categories.duplicate_radius_meters": "Two reports this close together count as the same problem.",
    "infrastructure_issues.tracking_token": "The code the resident types in to check on their report.",
    "infrastructure_issues.upvote_count": "How many people reported the same thing.",
    "infrastructure_issues.location": "Where it is, as a point on the map.",
    "corruption_reports.geohash": "Roughly where, to about a kilometre. Never the exact spot - that would point at whoever filmed it.",
    "corruption_reports.accused_designation": "The job title complained about. Never a person's name.",
    "corruption_reports.moderation_status": "Whether a moderator has let it be published yet.",
    "corruption_reports.public_status_badge": "What the public sees: an unverified allegation until a watchdog says otherwise.",
    "corruption_reports.taken_down_at": "Set if an objection was upheld and the report was withdrawn.",
    "content_grievances.ticket": "The number the complainant quotes to follow their complaint.",
    "content_grievances.acknowledged_at": "The 24-hour clock the law sets.",
    "content_grievances.resolved_at": "The 15-day clock the law sets.",
    "emergency_reports.is_restricted": "Sealed. Once set, it can never be unset - the database forbids it.",
    "emergency_reports.original_sha256": "A fingerprint of the untouched file, so tampering would show.",
    "fir_records.fir_number": "The station's own number, in its own yearly sequence.",
    "fir_records.is_zero_fir": "Registered here, then transferred - a station may not turn someone away for being out of area.",
    "fir_records.investigation_deadline": "When the investigation is legally overdue.",
    "station_diary_entries.serial_no": "The line number in that station's diary that day.",
    "challans.issued_by_user_id": "The officer who decided. Never blank.",
    "audit_log.actor_user_id": "Which official.",
    "audit_log.entity_id": "What they acted on.",
    "users.role": "What this person is allowed to see. A moderator cannot open police evidence, and vice versa.",
    "users.police_station_id": "Which station they are posted to. Officers see only their own station's work.",
}

# Columns that point at another table without a database-level foreign key, so the explorer can
# still show a name instead of an identifier. Most are deliberate: an official's ward posting
# must survive a ward being redrawn rather than cascading their account away, so it is a
# reference in meaning but not a constraint. Matched on column name across every table.
SOFT_REFERENCES = {
    "ward_id": "wards",
    "jurisdiction_ward_id": "wards",
    "police_station_id": "police_stations",
    "station_id": "police_stations",
    "fir_id": "fir_records",
    "actor_user_id": "users",
    "officer_user_id": "users",
    "reviewed_by_user_id": "users",
    "second_reviewer_user_id": "users",
    "decided_by_user_id": "users",
    "registered_by_user_id": "users",
    "investigating_officer_id": "users",
    "issued_by_user_id": "users",
}

# Deliberately absent from the map above: media_id and resolution_proof_media_id are storage
# keys rather than rows, camera_id is a camera's name, and audit_log.entity_id can point at any
# table at all, so there is nothing single to resolve it against.

APPEND_ONLY = {"audit_log", "chain_of_custody_entries", "station_diary_entries", "case_diary_entries"}

# Not shown at all: Alembic's own bookkeeping, which means nothing to a reader.
HIDDEN_TABLES = {"alembic_version"}


def humanise(column: str) -> str:
    """`accused_department` -> `Accused department`. Used for every column without a note."""
    words = column.replace("_id", "").replace("_", " ").strip()
    return (words[:1].upper() + words[1:]) if words else column
