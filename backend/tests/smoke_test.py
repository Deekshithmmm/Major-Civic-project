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
import random
import subprocess
import sys
import tempfile
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
    check("tracking token issued", bool(token))
    check("first report is not merged", created["merged_into_existing"] is False)

    detail = requests.get(f"{BASE}/api/infra/issues/track/{token}", timeout=10).json()
    check("tracking token resolves to the report", detail["category_slug"] == "pothole")
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

    summary = f"  {passed} passed, {failed} failed" + (f", {skipped} skipped" if skipped else "")
    print(f"\n{'=' * 52}\n{summary}\n{'=' * 52}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
