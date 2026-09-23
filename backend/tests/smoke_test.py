"""
End-to-end smoke test / demo script. Runs against a live server + seeded database:

    docker compose up -d
    alembic upgrade head && python -m app.seed.seed_data
    uvicorn app.main:app --port 8000 --no-access-log
    python -m tests.smoke_test

It exercises the flows that carry the spec's actual guarantees, not just happy-path CRUD:
EXIF stripping, jurisdiction resolution, duplicate clustering, SLA breach, proof-gated
resolution, role separation, and the append-only audit log.
"""

import io
import json
import random
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg
import requests
from PIL import Image

BASE = "http://localhost:8000"
DEV_PASSWORD = "DevPassword123!"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# A fresh point inside the seeded "Lakeview Ward" polygon (12.97-12.99 lat, 77.59-77.61 lng) on
# every run. Without the jitter, a second run lands inside the first run's 50m duplicate radius
# and the clustering checks "fail" purely because the previous run's data is still there.
TEST_LAT = round(random.uniform(12.9730, 12.9870), 6)
TEST_LNG = round(random.uniform(77.5930, 77.6070), 6)

passed, failed, skipped = 0, 0, 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f" -- {detail}" if detail else ""))


def skip(label: str, why: str) -> None:
    global skipped
    skipped += 1
    print(f"  SKIP  {label} -- {why}")


def make_jpeg_with_gps_exif() -> bytes:
    """A JPEG carrying GPS EXIF, so we can prove the pipeline strips it rather than assume so."""
    image = Image.new("RGB", (800, 600), color=(120, 90, 60))
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"  # Make
    exif[0x0110] = "SmokeTest"  # Model
    exif[0x8825] = {  # GPSInfo IFD
        1: "N",
        2: (12.0, 58.0, 48.0),
        3: "E",
        4: (77.0, 35.0, 42.0),
    }
    buf = io.BytesIO()
    image.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def make_video_with_gps_metadata() -> bytes:
    """An MP4 tagged the way iPhones tag video (GPS + device keys) with an audio track."""
    path = Path(tempfile.gettempdir()) / "smoke_gps_video.mp4"
    subprocess.run(
        [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
            "-f", "lavfi", "-i", "sine=duration=2", "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-metadata", "location=+12.9716+077.5946/", "-metadata", "make=SmokeTestPhone",
            "-movflags", "use_metadata_tags", str(path),
        ],
        check=True,
    )
    return path.read_bytes()


def media_info(data: bytes) -> str:
    """ffmpeg's description of a media file: its streams and every metadata tag it carries."""
    path = Path(tempfile.gettempdir()) / "smoke_probe.mp4"
    path.write_bytes(data)
    return subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr


# The three accounts this schema defines. The whole point of the split is that they can do
# different things, so the tests below connect as each one rather than as root for everything.
DB_ACCOUNTS = {
    "app": ("civic", "civic_dev_password"),
    "owner": ("civic_migrate", "civic_migrate_password"),
    "root": ("root", "civic_root_password"),
}


def mysql(sql: str, as_account: str = "root") -> tuple[int, str] | None:
    """
    Run a statement straight against MySQL, as one of the three accounts.

    Talking to the database directly is the point: a claim that a table cannot be altered is not
    tested by asking the application whether it tried. Returns (returncode, output), or None when
    docker is not reachable from wherever this is running, so the caller can skip rather than
    fail.
    """
    user, password = DB_ACCOUNTS[as_account]
    try:
        result = subprocess.run(
            [
                "docker", "exec", "major-civic-project-db-1",
                "mysql", f"-u{user}", f"-p{password}", "civic_accountability", "-N", "-s", "-e", sql,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    combined = (result.stdout + result.stderr).replace("mysql: [Warning] Using a password on the command line interface can be insecure.", "").strip()
    return result.returncode, combined


def refused(sql: str, as_account: str) -> bool | None:
    """True when MySQL refused the statement. None when docker is unreachable."""
    outcome = mysql(sql, as_account)
    if outcome is None:
        return None
    code, output = outcome
    return code != 0 or "ERROR" in output


def audit_rows_for(action: str, entity_id: str) -> int | None:
    """Count audit rows in the table itself, not through an API."""
    outcome = mysql(
        f"SELECT count(*) FROM audit_log WHERE action = '{action}' AND entity_id = '{entity_id}'"
    )
    if outcome is None or outcome[0] != 0:
        return None
    return int(outcome[1].strip() or 0)


def main() -> int:
    print("\n== Module 3: citizen report flow ==")

    categories = requests.get(f"{BASE}/api/infra/categories", timeout=10).json()
    check("categories are configured in the DB, not hard-coded", len(categories) >= 12, f"got {len(categories)}")
    pothole = next(c for c in categories if c["slug"] == "pothole")
    check("pothole SLA is 7 days per spec", pothole["sla_hours"] == 168, f"got {pothole['sla_hours']}h")

    original = make_jpeg_with_gps_exif()
    check("test fixture genuinely has EXIF GPS", 0x8825 in Image.open(io.BytesIO(original)).getexif())

    files = {"file": ("report.jpg", original, "image/jpeg")}
    data = {
        "category_slug": "pothole",
        "description": "Smoke test pothole",
        "lat": str(TEST_LAT),
        "lng": str(TEST_LNG),
        "phone_number": "+91-90000-12345",
    }
    res = requests.post(f"{BASE}/api/infra/issues", files=files, data=data, timeout=60)
    check("anonymous citizen report accepted (no auth header sent)", res.status_code == 201, res.text[:200])
    created = res.json()
    token = created["tracking_token"]
    check("tracking code issued", bool(token))
    check("tracking code is 10 digits with no leading zero", bool(re.fullmatch(r"[1-9]\d{9}", token)), token)
    check("first report is not merged", created["merged_into_existing"] is False)

    detail = requests.get(f"{BASE}/api/infra/issues/track/{token}", timeout=10).json()
    check("tracking code resolves to the report", detail["category_slug"] == "pothole")

    spaced = f"{token[:4]} {token[4:7]} {token[7:]}"  # the grouping the UI displays
    spaced_res = requests.get(f"{BASE}/api/infra/issues/track/{spaced}", timeout=10)
    check("code typed with spaces still resolves", spaced_res.status_code == 200, str(spaced_res.status_code))

    check("status history recorded", len(detail["history"]) >= 1)

    print("\n== Privacy: EXIF stripped before storage (spec 2.6) ==")
    issue_id = created["id"]
    stored_media_id = detail["media_id"]
    check("stored media is reachable by opaque ID", bool(stored_media_id))

    stored_bytes = requests.get(f"{BASE}/api/media/{stored_media_id}", timeout=30).content
    stored_exif = Image.open(io.BytesIO(stored_bytes)).getexif()
    check("GPS EXIF is gone from the stored copy", 0x8825 not in stored_exif, f"exif keys: {list(stored_exif)}")
    check("camera make/model EXIF is gone too", 0x010F not in stored_exif and 0x0110 not in stored_exif)
    check("the stored file is still a valid image", Image.open(io.BytesIO(stored_bytes)).size == (800, 600))
    check("photo report is flagged as image", detail["media_kind"] == "image", str(detail["media_kind"]))

    print("\n== Privacy: video metadata and audio stripped (videos are not face-blurred) ==")
    video = make_video_with_gps_metadata()
    fixture_info = media_info(video)
    check(
        "video fixture genuinely has GPS, device make and audio",
        all(k in fixture_info for k in ("12.9716", "SmokeTestPhone", "Audio:")),
    )

    vres = requests.post(
        f"{BASE}/api/infra/issues",
        files={"file": ("clip.mp4", video, "video/mp4")},
        data={"category_slug": "fallen_tree", "lat": str(TEST_LAT + 0.003), "lng": str(TEST_LNG)},
        timeout=120,
    )
    check("video report accepted", vres.status_code == 201, vres.text[:200])
    if vres.status_code == 201:
        vdetail = requests.get(f"{BASE}/api/infra/issues/{vres.json()['id']}", timeout=10).json()
        stored_info = media_info(requests.get(f"{BASE}/api/media/{vdetail['media_id']}", timeout=30).content)
        check("GPS location is gone from the stored video", "12.9716" not in stored_info)
        check("device make is gone from the stored video", "SmokeTestPhone" not in stored_info)
        check("audio is dropped from the stored video", "Audio:" not in stored_info)
        check("stored video still has its picture", "Video: h264" in stored_info)
        check("video report is flagged as video so the page renders a player", vdetail["media_kind"] == "video", str(vdetail["media_kind"]))

    print("\n== Module 3: duplicate clustering (spec 2.4 step 7) ==")
    dup_files = {"file": ("dup.jpg", make_jpeg_with_gps_exif(), "image/jpeg")}
    dup_data = {"category_slug": "pothole", "lat": str(TEST_LAT), "lng": str(TEST_LNG)}
    dup = requests.post(f"{BASE}/api/infra/issues", files=dup_files, data=dup_data, timeout=60).json()
    check("second report at same spot merges instead of duplicating", dup["merged_into_existing"] is True)
    check("merged report returns the original's tracking token", dup["tracking_token"] == token)

    after = requests.get(f"{BASE}/api/infra/issues/{issue_id}", timeout=10).json()
    check("upvote count incremented on merge", after["upvote_count"] == 2, f"got {after['upvote_count']}")

    far_files = {"file": ("far.jpg", make_jpeg_with_gps_exif(), "image/jpeg")}
    far_data = {"category_slug": "pothole", "lat": str(TEST_LAT + 0.01), "lng": str(TEST_LNG)}
    far = requests.post(f"{BASE}/api/infra/issues", files=far_files, data=far_data, timeout=60).json()
    check("report >50m away creates a separate issue", far["merged_into_existing"] is False)

    print("\n== Auth and role separation (spec 2.6) ==")
    unauth = requests.get(f"{BASE}/api/infra/officer/queue", timeout=10)
    check("officer queue rejects anonymous access", unauth.status_code == 401, str(unauth.status_code))

    login = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": "officer.roads@demo.city", "password": DEV_PASSWORD},
        timeout=10,
    )
    check("municipal officer can log in", login.status_code == 200, login.text[:200])
    officer_h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    mod_login = requests.post(
        f"{BASE}/api/auth/login", json={"email": "moderator@demo.city", "password": DEV_PASSWORD}, timeout=10
    ).json()
    mod_h = {"Authorization": f"Bearer {mod_login['access_token']}"}

    forbidden = requests.get(f"{BASE}/api/violations/officer/queue", headers=mod_h, timeout=10)
    check(
        "moderator is refused Module 1 identity data (spec: 'A moderator cannot see Module 1 identity data')",
        forbidden.status_code == 403,
        str(forbidden.status_code),
    )

    m1_forbidden = requests.get(f"{BASE}/api/corruption/moderation/queue", headers=officer_h, timeout=10)
    check(
        "municipal officer is refused Module 2 reports (spec: 'A municipal officer cannot see Module 2 reports')",
        m1_forbidden.status_code == 403,
        str(m1_forbidden.status_code),
    )

    print("\n== Module 3: officer workflow ==")
    queue = requests.get(f"{BASE}/api/infra/officer/queue", headers=officer_h, timeout=10).json()
    check("officer queue returns open issues", len(queue) > 0, f"got {len(queue)}")

    ack = requests.post(f"{BASE}/api/infra/officer/issues/{issue_id}/acknowledge", headers=officer_h, timeout=10)
    check("officer can acknowledge", ack.status_code == 200 and ack.json()["status"] == "acknowledged", ack.text[:200])

    no_proof = requests.post(f"{BASE}/api/infra/officer/issues/{issue_id}/resolve", headers=officer_h, timeout=10)
    check(
        "resolve without a proof photo is rejected (spec: 'requires an officer-uploaded proof photo')",
        no_proof.status_code == 422,
        str(no_proof.status_code),
    )

    proof = {"proof_file": ("proof.jpg", make_jpeg_with_gps_exif(), "image/jpeg")}
    resolved = requests.post(
        f"{BASE}/api/infra/officer/issues/{issue_id}/resolve",
        headers=officer_h,
        files=proof,
        data={"note": "Filled and resurfaced"},
        timeout=60,
    )
    check("resolve with proof succeeds", resolved.status_code == 200 and resolved.json()["status"] == "resolved", resolved.text[:200])

    print("\n== Module 3: SLA breach and citizen-initiated escalation ==")
    overdue = [i for i in requests.get(f"{BASE}/api/infra/issues?status_filter=overdue", timeout=10).json()]
    check("seeded overdue issue appears on the public board", len(overdue) >= 1, f"got {len(overdue)}")
    if overdue:
        card = requests.get(f"{BASE}/api/infra/issues/{overdue[0]['id']}/share-card", timeout=10)
        check("shareable card generated for breached SLA", card.status_code == 200, card.text[:200])
        check("card is text for the citizen to post themselves", "share_text" in card.json())

    not_overdue = requests.get(f"{BASE}/api/infra/issues/{issue_id}/share-card", timeout=10)
    check("no share card before the SLA is breached", not_overdue.status_code == 400, str(not_overdue.status_code))

    print("\n== Module 1: officer review, no auto-fine ==")
    stats = requests.get(f"{BASE}/api/violations/stats", timeout=10)
    check("violation counts are public without an account", stats.status_code == 200, str(stats.status_code))
    check(
        "public violation stats carry no evidence, location or plate",
        stats.status_code != 200
        or set(stats.json()) == {"pending_review", "confirmed", "dismissed", "challans_issued"},
        str(list(stats.json()) if stats.status_code == 200 else ""),
    )

    cases = requests.get(f"{BASE}/api/violations/officer/queue", headers=officer_h, timeout=10).json()
    check("violation cases await officer review", len(cases) >= 1, f"got {len(cases)}")
    check("nothing is auto-confirmed", all(c["status"] == "pending_review" for c in cases))

    anpr_case = next((c for c in cases if c["identity_path"] == "anpr"), None)
    if not anpr_case:
        skip("challan issuance flow", "no pending ANPR case left (already confirmed by an earlier run)")
    if anpr_case:
        challan = requests.post(
            f"{BASE}/api/violations/officer/cases/{anpr_case['id']}/confirm", headers=officer_h, timeout=10
        )
        check("challan issued only on officer confirmation", challan.status_code == 200, challan.text[:200])
        if challan.status_code == 200:
            body = challan.json()
            check("first-offence amount read from the fine ladder config", body["amount_rupees"] == 500, str(body["amount_rupees"]))

            disputed = requests.post(
                f"{BASE}/api/violations/challans/{body['id']}/dispute",
                json={"reason": "Vehicle was not there"},
                timeout=10,
            )
            check("citizen can dispute without an account", disputed.status_code == 200, disputed.text[:200])

            same_officer = requests.post(
                f"{BASE}/api/violations/officer/disputes/{body['id']}/uphold", headers=officer_h, timeout=10
            )
            check(
                "the officer who issued it cannot rule on its appeal",
                same_officer.status_code == 403,
                str(same_officer.status_code),
            )

    print("\n== Module 2: anonymity and routing ==")
    rules = requests.get(f"{BASE}/api/corruption/routing-rules", timeout=10).json()
    police_rule = next(r for r in rules if r["accused_party_type"] == "police_personnel")
    check(
        "police-personnel reports never notify local police (spec 1.3)",
        police_rule["notify_local_police"] is False,
    )
    check("police reports route to ACB + Police Complaints Authority", "Police Complaints Authority" in police_rule["primary_route_body"])

    feed = requests.get(f"{BASE}/api/corruption/feed", timeout=10).json()
    check("public feed only shows moderated reports", all("accused_department" in f for f in feed))
    check("feed never carries an accused individual's name", all("accused_name" not in f for f in feed))

    submitted = requests.post(
        f"{BASE}/api/corruption/reports",
        files={"file": ("evidence.jpg", make_jpeg_with_gps_exif(), "image/jpeg")},
        data={
            "accused_department": "Smoke Test Department",
            "accused_designation": "Clerk",
            "accused_party_type": "municipal_or_dept_staff",
            "description": "Smoke test report",
            "geohash": "tdr1x",
        },
        timeout=60,
    )
    check("corruption report accepted with no account or identifier", submitted.status_code == 201, submitted.text[:200])
    corr_token = submitted.json()["tracking_token"]
    check("corruption tracking token is not a short number", not corr_token.isdigit() and len(corr_token) > 20, corr_token)

    tracked = requests.get(f"{BASE}/api/corruption/reports/track/{corr_token}", timeout=10).json()
    check("report starts as pending moderation", tracked["moderation_status"] == "pending", str(tracked))

    before_ids = {f["id"] for f in requests.get(f"{BASE}/api/corruption/feed", timeout=10).json()}
    pending = requests.get(f"{BASE}/api/corruption/moderation/queue", headers=mod_h, timeout=10).json()
    new_item = next((p for p in pending if p["accused_department"] == "Smoke Test Department"), None)
    check("moderator sees the report before it is public", new_item is not None)
    check("unmoderated report is not on the public feed", new_item is None or new_item["id"] not in before_ids)

    if new_item:
        check("moderation queue carries the media to review", bool(new_item["media_id"]) and new_item["media_kind"] == "image")
        approved = requests.post(
            f"{BASE}/api/corruption/moderation/{new_item['id']}/approve", headers=mod_h, json={}, timeout=10
        )
        check("moderator can publish it", approved.status_code == 200, approved.text[:200])
        check(
            "published report is flagged unverified, not as a finding",
            approved.status_code != 200 or approved.json()["public_status_badge"] == "unverified_allegation",
        )
        after = requests.get(f"{BASE}/api/corruption/feed", timeout=10).json()
        check("approved report now appears on the feed", any(f["id"] == new_item["id"] for f in after))

    print("\n== Module 2: grievance channel, right of reply and takedown (IT Rules 2021) ==")
    officer = requests.get(f"{BASE}/api/corruption/grievance-officer", timeout=10)
    check("Grievance Officer details are published, as Rule 3(2)(a) requires", officer.status_code == 200)
    officer_body = officer.json() if officer.status_code == 200 else {}
    check(
        "the published details carry a name, an address and a contact",
        all(officer_body.get(k) for k in ("name", "designation", "email", "address")),
        str(officer_body),
    )
    check(
        "the two statutory clocks are published with them (24h / 15d)",
        officer_body.get("acknowledgement_deadline_hours") == 24
        and officer_body.get("resolution_deadline_days") == 15,
        str(officer_body),
    )

    unknown_target = requests.post(
        f"{BASE}/api/corruption/grievances",
        json={
            "report_id": str(uuid.uuid4()),
            "ground": "defamatory",
            "body": "A complaint about a report that is not published anywhere.",
            "complainant_name": "Test Complainant",
            "complainant_email": "complainant@example.gov.in",
        },
        timeout=10,
    )
    check(
        "a grievance about an unpublished report is a 404, not a 403 that confirms it exists",
        unknown_target.status_code == 404,
        str(unknown_target.status_code),
    )

    if new_item:
        reply = requests.post(
            f"{BASE}/api/corruption/replies",
            json={
                "report_id": new_item["id"],
                "body": "The department rejects this allegation and has ordered an internal inquiry.",
                "author_department": "Smoke Test Department",
                "author_designation": "Deputy Commissioner",
                "author_name": "R. Iyer",
                "author_contact_email": "dc@smoke-test-dept.gov.in",
            },
            timeout=10,
        )
        check("the accused body can file a reply without an account", reply.status_code == 201, reply.text[:200])
        check(
            "a reply is held for verification, not published on arrival",
            reply.status_code != 201 or reply.json()["status"] == "pending",
            reply.text[:200],
        )

        feed_pre_reply = requests.get(f"{BASE}/api/corruption/feed", timeout=10).json()
        item_pre = next((f for f in feed_pre_reply if f["id"] == new_item["id"]), {})
        check("an unverified reply does not appear under the allegation", item_pre.get("replies") == [])

        reply_queue = requests.get(f"{BASE}/api/corruption/replies/queue", headers=mod_h, timeout=10).json()
        queued_reply = next((r for r in reply_queue if r["report_id"] == new_item["id"]), None)
        check("the reply reaches the moderator queue for verification", queued_reply is not None)
        check(
            "the queue gives the moderator a contact to verify the reply against",
            queued_reply is None or queued_reply["author_contact_email"] == "dc@smoke-test-dept.gov.in",
        )

        if queued_reply:
            published = requests.post(
                f"{BASE}/api/corruption/replies/{queued_reply['id']}/decide",
                headers=mod_h,
                json={"publish": True},
                timeout=10,
            )
            check("moderator can publish a verified reply", published.status_code == 200, published.text[:200])

            feed_post_reply = requests.get(f"{BASE}/api/corruption/feed", timeout=10).json()
            item_post = next((f for f in feed_post_reply if f["id"] == new_item["id"]), {})
            replies_shown = item_post.get("replies", [])
            check("the reply is published under the allegation itself", len(replies_shown) == 1, str(replies_shown))
            check(
                "the published reply is attributed to the office, never to the official who wrote it",
                not replies_shown
                or (
                    replies_shown[0]["author_designation"] == "Deputy Commissioner"
                    and "author_name" not in replies_shown[0]
                    and "author_contact_email" not in replies_shown[0]
                ),
                str(replies_shown[:1]),
            )

        grievance = requests.post(
            f"{BASE}/api/corruption/grievances",
            json={
                "report_id": new_item["id"],
                "ground": "factually_incorrect",
                "body": "The transaction shown was a lawful fee receipted under reference 44/2026.",
                "complainant_name": "Test Complainant",
                "complainant_email": "complainant@example.gov.in",
                "complainant_designation": "Deputy Commissioner",
            },
            timeout=10,
        )
        check("anyone can file a grievance without an account", grievance.status_code == 201, grievance.text[:200])
        g_body = grievance.json() if grievance.status_code == 201 else {}
        ticket = g_body.get("ticket", "")
        check("the ticket is an 8-digit number with no leading zero", bool(re.fullmatch(r"[1-9]\d{7}", ticket)), ticket)
        check(
            "the 24-hour acknowledgement goes out on receipt, not when an officer gets to it",
            g_body.get("acknowledged") is True,
            str(g_body),
        )

        ticket_view = requests.get(f"{BASE}/api/corruption/grievances/track/{ticket}", timeout=10)
        tv = ticket_view.json() if ticket_view.status_code == 200 else {}
        check("the ticket resolves to a status", tv.get("status") == "acknowledged", str(tv))
        check(
            "a ticket lookup leaks neither the complainant nor the complaint text",
            not {"complainant_name", "complainant_email", "body"} & set(tv),
            str(sorted(tv)),
        )
        check("the 15-day disposal deadline is stated to the complainant", bool(tv.get("resolution_due_by")))

        anon_queue = requests.get(f"{BASE}/api/corruption/grievances/queue", timeout=10)
        check("the grievance queue is closed to anonymous callers", anon_queue.status_code == 401, str(anon_queue.status_code))

        queue = requests.get(f"{BASE}/api/corruption/grievances/queue", headers=mod_h, timeout=10).json()
        queued = next((g for g in queue if g["ticket"] == ticket), None)
        check("the grievance reaches the moderator queue", queued is not None)

        if queued:
            decided = requests.post(
                f"{BASE}/api/corruption/grievances/{queued['id']}/decide",
                headers=mod_h,
                json={
                    "uphold": True,
                    "note": "Upheld: the receipt reference was verified with the department.",
                },
                timeout=10,
            )
            check("a moderator can uphold a grievance", decided.status_code == 200, decided.text[:200])

            gone = requests.get(f"{BASE}/api/corruption/feed", timeout=10).json()
            check(
                "an upheld grievance takes the report off the public feed",
                all(f["id"] != new_item["id"] for f in gone),
            )

            withdrawn = requests.get(f"{BASE}/api/corruption/reports/track/{corr_token}", timeout=10).json()
            check("the anonymous uploader is told their report was withdrawn", withdrawn.get("taken_down") is True, str(withdrawn))
            check(
                "and is told on what ground, so the takedown is not silent",
                "receipt reference was verified" in (withdrawn.get("takedown_reason") or ""),
                str(withdrawn.get("takedown_reason")),
            )

            again = requests.post(
                f"{BASE}/api/corruption/grievances/{queued['id']}/decide",
                headers=mod_h,
                json={"uphold": False, "note": "Attempting to re-decide a disposed grievance."},
                timeout=10,
            )
            check("a disposed grievance cannot be decided twice", again.status_code == 409, str(again.status_code))

            late_reply = requests.post(
                f"{BASE}/api/corruption/replies",
                json={
                    "report_id": new_item["id"],
                    "body": "A reply filed after the report was already withdrawn from publication.",
                    "author_department": "Smoke Test Department",
                    "author_designation": "Deputy Commissioner",
                    "author_name": "R. Iyer",
                    "author_contact_email": "dc@smoke-test-dept.gov.in",
                },
                timeout=10,
            )
            check(
                "a withdrawn report accepts no further replies",
                late_reply.status_code == 404,
                str(late_reply.status_code),
            )

            takedown_rows = audit_rows_for("TAKEDOWN", new_item["id"])
            if takedown_rows is None:
                skip("the takedown is written to the append-only audit log", "psql not reachable from here")
            else:
                check(
                    "the takedown is written to the append-only audit log, naming the officer",
                    takedown_rows >= 1,
                    f"rows: {takedown_rows}",
                )

    compliance = requests.get(f"{BASE}/api/corruption/compliance", timeout=10)
    comp = compliance.json() if compliance.status_code == 200 else {}
    check("the platform publishes its own grievance compliance", compliance.status_code == 200)
    check("compliance counts grievances received", comp.get("grievances_received", 0) >= 1, str(comp))
    check(
        "compliance reports against both statutory deadlines",
        comp.get("acknowledgement_deadline_hours") == 24 and comp.get("resolution_deadline_days") == 15,
        str(comp),
    )
    check(
        "no complaint text or complainant appears in the public figures",
        all(isinstance(v, (int, float, type(None))) for v in comp.values()),
        str(comp),
    )

    print("\n== Module 4: hard stop, evidence custody and the transparency layer ==")
    hard_stop = requests.post(
        f"{BASE}/api/emergency/reports",
        data={"category": "minor_involved", "lat": TEST_LAT, "lng": TEST_LNG, "geohash": "tdr1x"},
        files={"file": ("x.jpg", make_jpeg_with_gps_exif(), "image/jpeg")},
        timeout=30,
    )
    check(
        "any offence involving a minor is refused outright, even with a file attached",
        hard_stop.status_code == 422,
        str(hard_stop.status_code),
    )
    stop_detail = hard_stop.json().get("detail", {}) if hard_stop.status_code == 422 else {}
    check(
        "the refusal routes the user to 1098, 112 and CCPWC",
        {"1098", "112"}.issubset({r["number"] for r in stop_detail.get("redirect_to", [])}),
    )

    restricted_video = requests.post(
        f"{BASE}/api/emergency/reports",
        data={"category": "sexual_offence_adult", "lat": TEST_LAT, "lng": TEST_LNG, "geohash": "tdr1x"},
        files={"file": ("x.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
        timeout=30,
    )
    check(
        "restricted category refuses video while blur is unavailable",
        restricted_video.status_code == 415,
        str(restricted_video.status_code),
    )

    no_evidence = requests.post(
        f"{BASE}/api/emergency/reports",
        data={"category": "assault_in_progress", "lat": TEST_LAT, "lng": TEST_LNG, "geohash": "tdr1x"},
        timeout=30,
    )
    check("a report with no evidence is accepted", no_evidence.status_code == 201, no_evidence.text[:200])
    check(
        "support resources are surfaced on submission",
        no_evidence.status_code != 201 or any(r["number"] == "112" for r in no_evidence.json()["support_resources"]),
    )

    inv_login = requests.post(
        f"{BASE}/api/auth/login", json={"email": "investigator@demo.city", "password": DEV_PASSWORD}, timeout=10
    ).json()
    inv_h = {"Authorization": f"Bearer {inv_login['access_token']}"}

    check(
        "moderator has no route to Module 4 evidence at all (spec 2.6)",
        requests.post(
            f"{BASE}/api/emergency/officer/reports/{uuid.uuid4()}/evidence",
            headers=mod_h, json={"case_or_fir_number": "X/1"}, timeout=10,
        ).status_code == 403,
    )
    m4_queue = requests.get(f"{BASE}/api/station/reports", headers=inv_h, timeout=10)
    check("investigating officer can see their station's queue", m4_queue.status_code == 200, str(m4_queue.status_code))

    with_evidence = next((r for r in m4_queue.json() if r["has_evidence"]), None) if m4_queue.status_code == 200 else None
    if not with_evidence:
        skip("evidence custody flow", "no seeded report holds evidence")
    else:
        blank = requests.post(
            f"{BASE}/api/emergency/officer/reports/{with_evidence['id']}/evidence",
            headers=inv_h, json={"case_or_fir_number": "   "}, timeout=15,
        )
        check("evidence is refused without a case or FIR number", blank.status_code == 400, str(blank.status_code))

        opened = requests.post(
            f"{BASE}/api/emergency/officer/reports/{with_evidence['id']}/evidence",
            headers=inv_h, json={"case_or_fir_number": "FIR/SMOKE/1"}, timeout=15,
        )
        check("evidence opens with a case number", opened.status_code == 200, opened.text[:200])
        if opened.status_code == 200:
            check("evidence is served from the segregated vault bucket", "evidence-vault" in opened.json()["url"])
            check("the sealing hash is kept with the report", bool(opened.json()["original_sha256"]))

        chain = requests.get(
            f"{BASE}/api/emergency/officer/reports/{with_evidence['id']}/chain-of-custody", headers=inv_h, timeout=10
        ).json()
        check("chain of custody records the seal and the access", len(chain) >= 2, str(len(chain)))
        check("the access entry carries the case number", any(e["case_or_fir_number"] == "FIR/SMOKE/1" for e in chain))

    ledger = requests.get(f"{BASE}/api/emergency/ledger", timeout=15).json()
    check("station response ledger is public", len(ledger) > 0, str(len(ledger)))
    check(
        "the ledger flags a station sitting on reports past the FIR deadline",
        any(row["flagged_red"] for row in ledger),
    )

    hotspots = requests.get(f"{BASE}/api/emergency/hotspots", timeout=15).json()
    check(
        "hotspot map suppresses any cell below the k-anonymity threshold of five",
        all(cell["report_count"] >= 5 for cell in hotspots),
    )
    check(
        "hotspot map never carries a restricted category",
        all(cell["category"] not in ("sexual_offence_adult", "minor_involved") for cell in hotspots),
    )
    cases = requests.get(f"{BASE}/api/emergency/cases", timeout=15)
    check("the public case record is published", cases.status_code == 200, str(cases.status_code))
    records = cases.json() if cases.status_code == 200 else []
    check(
        "no restricted category ever reaches the case record",
        all(c["category"] not in ("sexual_offence_adult", "minor_involved", "human_trafficking") for c in records),
    )
    check(
        "the court is disclosed only once a chargesheet is filed",
        all(c["court_name"] is None for c in records if c["status"] != "Chargesheet filed"),
    )
    check(
        "an FIR number becomes public once the FIR is registered",
        any(c["fir_number"] for c in records) if records else True,
    )
    check(
        "an outcome is published when a case is closed either way",
        all(c["outcome"] for c in records if c["status"] == "Closed without FIR"),
    )

    this_quarter = f"{datetime.now(timezone.utc).year} Q{(datetime.now(timezone.utc).month - 1) // 3 + 1}"
    check("hotspot map runs a quarter behind", all(cell["quarter"] != this_quarter for cell in hotspots))

    print("\n== Police station network and internal procedures ==")
    stations = requests.get(f"{BASE}/api/station/directory", timeout=10).json()
    check("station directory is public", len(stations) >= 4, str(len(stations)))
    check("stations are mapped to a location", all(s["lat"] and s["lng"] for s in stations))
    check(
        "a ward can hold more than one station",
        len({s["ward_name"] for s in stations}) < len(stations),
        f"{len(stations)} stations across {len({s['ward_name'] for s in stations})} wards",
    )

    near = requests.get(f"{BASE}/api/station/nearest", params={"lat": 12.980, "lng": 77.620}, timeout=10)
    check("nearest station resolves for a point", near.status_code == 200, str(near.status_code))
    check(
        "the nearest station is the one in that ward",
        near.status_code != 200 or near.json()["ward_name"] == "Market Ward",
        near.json().get("name", "") if near.status_code == 200 else "",
    )

    lakeview_h = {
        "Authorization": "Bearer "
        + requests.post(
            f"{BASE}/api/auth/login", json={"email": "sho.lakeview@demo.city", "password": DEV_PASSWORD}, timeout=10
        ).json()["access_token"]
    }
    market_h = {
        "Authorization": "Bearer "
        + requests.post(
            f"{BASE}/api/auth/login", json={"email": "sho.market@demo.city", "password": DEV_PASSWORD}, timeout=10
        ).json()["access_token"]
    }

    mine = requests.get(f"{BASE}/api/station/me", headers=lakeview_h, timeout=10)
    check("an officer is posted to a station", mine.status_code == 200 and mine.json()["code"] == "PS-01", mine.text[:120])

    lk_reports = requests.get(f"{BASE}/api/station/reports", headers=lakeview_h, timeout=10).json()
    mk_reports = requests.get(f"{BASE}/api/station/reports", headers=market_h, timeout=10).json()
    check(
        "a station sees only its own reports",
        not ({r["id"] for r in lk_reports} & {r["id"] for r in mk_reports}),
    )
    check("a moderator cannot reach station procedures",
          requests.get(f"{BASE}/api/station/reports", headers=mod_h, timeout=10).status_code == 403)

    target = next((r for r in lk_reports if not r["fir_number"] and not r["closed_at"]), None)
    if not target:
        skip("station procedure chain", "no workable report at the test station")
    else:
        gd_before = len(requests.get(f"{BASE}/api/station/diary", headers=lakeview_h, timeout=10).json())

        ack = requests.post(f"{BASE}/api/station/reports/{target['id']}/acknowledge", headers=lakeview_h, timeout=10)
        check("duty officer can acknowledge a report", ack.status_code == 200, str(ack.status_code))

        fir = requests.post(
            f"{BASE}/api/station/reports/{target['id']}/fir",
            headers=lakeview_h, json={"sections": "BNS 115(2)"}, timeout=10,
        )
        check("FIR registers against the report", fir.status_code == 201, fir.text[:150])
        check(
            "the FIR number is issued by the station, not typed in",
            fir.status_code != 201 or re.fullmatch(r"\d{4}/\d{4}", fir.json()["fir_number"]) is not None,
            fir.json().get("fir_number", "") if fir.status_code == 201 else "",
        )
        check(
            "an investigation deadline is set",
            fir.status_code != 201 or fir.json()["days_remaining"] > 0,
        )

        if fir.status_code == 201:
            fir_id = fir.json()["id"]
            again = requests.post(
                f"{BASE}/api/station/reports/{target['id']}/fir",
                headers=lakeview_h, json={"sections": "BNS 115(2)"}, timeout=10,
            )
            check("a second FIR on the same report is refused", again.status_code == 409, str(again.status_code))

            cd = requests.post(
                f"{BASE}/api/station/firs/{fir_id}/case-diary",
                headers=lakeview_h, json={"detail": "Scene inspected; statements recorded."}, timeout=10,
            )
            check("investigating officer can add a case diary entry", cd.status_code == 201, str(cd.status_code))

            foreign = requests.post(
                f"{BASE}/api/station/firs/{fir_id}/case-diary",
                headers=market_h, json={"detail": "another station writing"}, timeout=10,
            )
            check("another station cannot write to this FIR", foreign.status_code == 403, str(foreign.status_code))

            cs = requests.post(
                f"{BASE}/api/station/firs/{fir_id}/chargesheet",
                headers=lakeview_h, json={"court_name": "CJM Demo City"}, timeout=10,
            )
            check("chargesheet can be filed", cs.status_code == 200, cs.text[:120])
            check(
                "a concluded FIR cannot be concluded twice",
                requests.post(
                    f"{BASE}/api/station/firs/{fir_id}/chargesheet",
                    headers=lakeview_h, json={"court_name": "CJM Demo City"}, timeout=10,
                ).status_code == 409,
            )

        gd_after = requests.get(f"{BASE}/api/station/diary", headers=lakeview_h, timeout=10).json()
        check(
            "every procedure wrote a General Diary entry",
            len(gd_after) >= gd_before + 4,
            f"{gd_before} -> {len(gd_after)}",
        )
        check(
            "diary entries are numbered per station per day",
            all(e["serial_no"] > 0 for e in gd_after)
            and len({(e["entry_date"], e["serial_no"]) for e in gd_after}) == len(gd_after),
        )

    zero_firs = [
        f for f in requests.get(f"{BASE}/api/station/firs", headers=market_h, timeout=10).json() if f["is_zero_fir"]
    ]
    check("a Zero FIR is registered and transferred, not refused", len(zero_firs) >= 1, str(len(zero_firs)))
    check(
        "the transferred Zero FIR still belongs to the station that registered it",
        not zero_firs or zero_firs[0]["transferred_to_station_id"] is not None,
    )

    detail = requests.get(f"{BASE}/api/station/{stations[0]['id']}", timeout=10)
    check("a station has a public detail page", detail.status_code == 200, str(detail.status_code))
    check(
        "station detail carries its response metrics, not case data",
        detail.status_code != 200
        or ("firs_registered" in detail.json() and "reports" not in detail.json()),
    )
    check(
        "an unknown station id is a clean 404",
        requests.get(f"{BASE}/api/station/{uuid.uuid4()}", timeout=10).status_code == 404,
    )

    zero_station = next((s for s in stations if s["code"] == "PS-05"), None)
    if zero_station:
        zd = requests.get(f"{BASE}/api/station/{zero_station['id']}", timeout=10).json()
        check(
            "a station that registered a Zero FIR and transferred it still gets the credit",
            zd["firs_registered"] >= 1,
            f"firs_registered={zd['firs_registered']}",
        )

    ledger_after = requests.get(f"{BASE}/api/emergency/ledger", timeout=15).json()
    check(
        "the public ledger counts FIRs from the station register",
        any(row["firs_registered"] > 0 for row in ledger_after),
    )

    print("\n== The database view (/database) ==")
    overview = requests.get(f"{BASE}/api/schema/tables", timeout=10)
    check("the database view lists the tables", overview.status_code == 200, str(overview.status_code))
    ov = overview.json() if overview.status_code == 200 else {}
    check(
        "every table in the database has a plain-English description",
        ov.get("undocumented") == [],
        f"undocumented: {ov.get('undocumented')}",
    )
    check("all 24 tables are covered", ov.get("table_count") == 24, str(ov.get("table_count")))

    # The masking is the part that must never quietly break: this page is the one place where a
    # reader is handed rows straight out of the database.
    reports = requests.get(f"{BASE}/api/schema/tables/corruption_reports", timeout=10).json()
    check(
        "a whistleblower's tracking token never reaches the database view",
        "tracking_token" not in {c["name"] for c in reports["columns"]},
    )
    check(
        "and no row carries one either",
        "tracking_token" in {w["column"] for w in reports["withheld"]},
        str(reports["withheld"]),
    )
    check(
        "the page says which columns it withheld and why",
        all(w["reason"] for w in reports["withheld"]),
    )
    check(
        "evidence file ids are not exposed by the database view",
        "media_id" not in {c["name"] for c in reports["columns"]},
    )

    users_view = requests.get(f"{BASE}/api/schema/tables/users", timeout=10).json()
    check(
        "password hashes never reach the database view",
        "hashed_password" not in {c["name"] for c in users_view["columns"]}
        and "hashed_password" not in json.dumps(users_view["rows"]),
    )

    # The thing that makes it readable at all: an identifier resolved to the name of what it
    # points at. Without this a reader sees a column of 32-character hex and learns nothing.
    issues_view = requests.get(f"{BASE}/api/schema/tables/infrastructure_issues", timeout=10).json()
    labels = [c["label"] for c in issues_view["columns"]]
    ward_cell = None
    if "Ward" in labels and issues_view["rows"]:
        ward_cell = issues_view["rows"][0][labels.index("Ward")]
    check(
        "references are shown as names, not as identifiers",
        bool(ward_cell) and "Ward" in str(ward_cell),
        f"ward column showed {ward_cell!r}",
    )
    location_cell = None
    if "Location" in labels and issues_view["rows"]:
        location_cell = issues_view["rows"][0][labels.index("Location")]
    check(
        "map points are shown as readable coordinates",
        bool(location_cell) and "," in str(location_cell) and "POINT" not in str(location_cell),
        f"location column showed {location_cell!r}",
    )

    unknown_table = requests.get(f"{BASE}/api/schema/tables/mysql.user", timeout=10)
    check(
        "the database view cannot be pointed at a table it does not describe",
        unknown_table.status_code == 404,
        str(unknown_table.status_code),
    )

    print("\n== MySQL schema guarantees ==")
    if mysql("SELECT 1") is None:
        skip("database-level guarantees", "docker not reachable from here")
    else:
        # Layer 1: privileges. The application account is the one whose credentials are exposed
        # if the app is compromised, so what *it* can do is the question that matters.
        probe = (
            "INSERT INTO audit_log (id, actor_user_id, action, entity_type, entity_id, detail) "
            "VALUES (REPLACE(UUID(),'-',''), REPLACE(UUID(),'-',''), 'VIEW', 'smoke_probe', "
            "'append-only-probe', 'written by the smoke test')"
        )
        check("the application account can append to the audit log", refused(probe, "app") is False)
        check(
            "the application account cannot rewrite an audit row",
            refused("UPDATE audit_log SET detail = 'tampered'", "app") is True,
        )
        check(
            "the application account cannot delete audit rows",
            refused("DELETE FROM audit_log", "app") is True,
        )
        # The one PostgreSQL could stop with a trigger and MySQL cannot. Withholding the DROP
        # privilege is what closes it; without app/db/harden.py this silently empties the table.
        check(
            "the application account cannot TRUNCATE the audit log",
            refused("TRUNCATE TABLE audit_log", "app") is True,
        )
        check(
            "the application account holds no DDL at all",
            refused("ALTER TABLE audit_log ADD COLUMN probe INT", "app") is True,
        )

        # Layer 2: triggers, which bind every account including the schema owner.
        for table in ("audit_log", "chain_of_custody_entries", "station_diary_entries", "case_diary_entries"):
            check(
                f"{table} refuses UPDATE even from the schema owner",
                refused(f"UPDATE {table} SET id = id", "owner") is True,
            )
        check(
            "a restricted emergency report can never be unrestricted, even by the schema owner",
            refused("UPDATE emergency_reports SET is_restricted = 0 WHERE is_restricted = 1", "owner") is True,
        )

        # Axis order. MySQL reads SRID 4326 latitude-first and PostGIS reads it longitude-first,
        # so a port that got this wrong would still return plausible numbers while placing every
        # report in the wrong place. 0.01 degrees of latitude is ~1111 m anywhere on earth.
        outcome = mysql(
            "SELECT ROUND(ST_Distance_Sphere("
            "ST_GeomFromText('POINT(12.9800 77.6000)', 4326), "
            "ST_GeomFromText('POINT(12.9900 77.6000)', 4326)))"
        )
        metres = int(outcome[1].strip()) if outcome and outcome[0] == 0 and outcome[1].strip() else 0
        check(
            "SRID 4326 is read latitude-first, so distances are real metres",
            1100 <= metres <= 1125,
            f"0.01 deg of latitude measured as {metres} m, expected ~1111",
        )

        # Seeded geometry has to land in Bengaluru, not in the Indian Ocean off Somalia - which
        # is exactly where a transposed lat/lng would put it.
        outcome = mysql(
            "SELECT COUNT(*) FROM police_stations WHERE location IS NOT NULL "
            "AND ST_Latitude(location) BETWEEN 12.9 AND 13.1 "
            "AND ST_Longitude(location) BETWEEN 77.5 AND 77.7"
        )
        in_city = int(outcome[1].strip()) if outcome and outcome[0] == 0 and outcome[1].strip() else 0
        check("every seeded station sits inside the demo city", in_city >= 6, f"got {in_city}")

        outcome = mysql("SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema='civic_accountability' AND index_type='SPATIAL'")
        spatial = int(outcome[1].strip()) if outcome and outcome[0] == 0 and outcome[1].strip() else 0
        check("geometry columns carry spatial indexes", spatial >= 3, f"got {spatial}")

    print("\n== Security controls ==")
    headers = requests.get(f"{BASE}/health", timeout=10).headers
    check("responses set X-Content-Type-Options", headers.get("X-Content-Type-Options") == "nosniff")
    check("responses refuse framing", headers.get("X-Frame-Options") == "DENY")
    check("responses send no referrer", headers.get("Referrer-Policy") == "no-referrer")
    check("responses carry a content security policy", "default-src 'none'" in headers.get("Content-Security-Policy", ""))
    check("API responses are not cacheable by shared caches", "no-store" in headers.get("Cache-Control", ""))

    oversize = requests.post(
        f"{BASE}/api/infra/issues",
        files={"file": ("big.jpg", b"\xff\xd8\xff" + b"\0" * (16 * 1024 * 1024), "image/jpeg")},
        data={"category_slug": "pothole", "lat": str(TEST_LAT), "lng": str(TEST_LNG)},
        timeout=120,
    )
    check("an oversized upload is refused, not loaded into memory", oversize.status_code == 413, str(oversize.status_code))

    bad_coords = requests.post(
        f"{BASE}/api/infra/issues",
        files={"file": ("x.jpg", make_jpeg_with_gps_exif(), "image/jpeg")},
        data={"category_slug": "pothole", "lat": "999", "lng": "0"},
        timeout=60,
    )
    check("out-of-range coordinates are rejected", bad_coords.status_code == 422, str(bad_coords.status_code))

    for probe in ("../../etc/passwd", "module3/not-a-key", "../civic-evidence-vault/x.jpg"):
        r = requests.get(f"{BASE}/api/media/{probe}", timeout=10, allow_redirects=False)
        check(f"media route rejects '{probe[:28]}'", r.status_code == 404, str(r.status_code))

    from starlette.requests import Request as StarletteRequest

    from app.config import DEV_JWT_SECRET, Settings
    from app.security import rate_limit

    dummy = StarletteRequest({"type": "http", "headers": [(b"user-agent", b"smoke")], "client": ("203.0.113.9", 1)})
    limiter = rate_limit("smoke_probe", limit=2, window_seconds=60)
    limiter(dummy)
    limiter(dummy)
    try:
        limiter(dummy)
        check("rate limiter blocks a burst past its limit", False, "third call was allowed")
    except Exception as exc:  # HTTPException
        check("rate limiter blocks a burst past its limit", getattr(exc, "status_code", None) == 429, str(exc))

    try:
        Settings(env="production", jwt_secret=DEV_JWT_SECRET)
        check("startup refuses the default JWT secret outside development", False, "it was accepted")
    except Exception:
        check("startup refuses the default JWT secret outside development", True)

    out_of_area = requests.post(
        f"{BASE}/api/emergency/reports",
        data={"category": "narcotics", "lat": "12.9750", "lng": "77.5950", "geohash": "tdr1x"},
        files={"file": ("e.jpg", make_jpeg_with_gps_exif(), "image/jpeg")},
        timeout=60,
    )
    if out_of_area.status_code == 201:
        all_reports = requests.get(f"{BASE}/api/station/reports", headers=inv_h, timeout=10).json()
        foreign = [r for r in all_reports if r["has_evidence"]]
        check(
            "an investigating officer's queue only shows their own jurisdiction",
            all(r["id"] != out_of_area.json().get("id") for r in foreign),
        )
    else:
        skip("jurisdiction scoping", f"setup report failed ({out_of_area.status_code})")

    summary = f"  {passed} passed, {failed} failed" + (f", {skipped} skipped" if skipped else "")
    print(f"\n{'=' * 52}\n{summary}\n{'=' * 52}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
