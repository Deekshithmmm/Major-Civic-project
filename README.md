# Civic Accountability Platform

A four-module civic accountability platform for Indian municipal jurisdictions, built from the
project's build specification (see [`docs/spec-summary.md`](docs/spec-summary.md)). Synthetic data
only, no live government API integration, no real personal data.

> Draft engineering project. Not legal advice. See the spec's Appendix for the legal reasoning
> behind the design choices called out below.

## What's actually built vs. designed-but-unbuilt

Per the spec's own scope warning (Part 3.2): a complete small system demonstrates more than four
half-built ones. This repo currently implements **shared plumbing + Module 3 (civic infrastructure
reporting) end to end**, and ships **schemas, routing tables, and API stubs** for Modules 1, 2, and 4
so the design is documented and reviewable without pretending it's production-ready.

| Module | Status |
|---|---|
| Shared plumbing (auth, DB, PostGIS jurisdictions, audit log, storage, media pipeline) | Built |
| Module 3 — Civic infrastructure reporting | **Built end to end**, UI included |
| Module 1 — Violation detection & enforcement assist | Backend built: officer review queue, confirm/reclassify/dismiss, challan issuance off a config-driven fine ladder, citizen upload, dispute + second-officer appeal. **No YOLOv8 detection and no ANPR/OCR** — cases come from seed data or citizen uploads, and ANPR-path cases have no plate resolved. No UI. |
| Module 2 — Anonymous corruption reporting | Backend built: anonymous upload, routing-rules table, moderation queue, public feed, status badges, tracking tokens. **Not built:** uploader-driven extra blur regions, audio muting, device-level rate limiting, takedown/right-of-reply, Grievance Officer workflow. No UI. |
| Module 4 — Emergency incident reporting & evidence vault | **Schema and routing table only, no routes.** The DB-level safety constraints *are* live (append-only chain of custody, irreversible `is_restricted` flag). Everything else — triage screen, vault, chain of custody, transparency layer — is unbuilt by design; see the warning below. |

### Before anyone implements Module 4

Module 4 is the one module where a half-built version is worse than none. Its routes are
deliberately absent, not merely unfinished. Do not add any endpoint that writes to
`emergency_reports` until all of these exist:

- A **separate evidence-vault bucket** with its own access policy, retention schedule and
  encryption key — never the general media bucket these other modules use.
- **Hashing before processing** (SHA-256 of the original, client-side) — the chain of custody is
  worthless if the first hash is taken after the server has already re-encoded the file.
- **Storage-layer role separation**, not just the route dependencies used elsewhere in this repo.
  Moderators must have no path to this data at all.
- The **hard stop for any offence involving a minor**, enforced *before* any bytes are accepted.
  Accepting that upload "to forward it" is itself an offence under POCSO and IT Act 67B. The rule
  is already seeded in `emergency_routing_rules` (`is_hard_stop = true`).
- Its **own irreversible face blur for sexual-offence footage**. The shared media pipeline no
  longer blurs video at all (removed for speed), so Module 4 cannot inherit that protection from
  it, and the spec makes blur at ingestion mandatory for these reports.

## Why the design looks like this

Four things in a typical "AI civic app" pitch don't survive contact with Indian law, and this project
deliberately routes around them. Full reasoning is in the spec (Part 1); short version:

1. **No face-to-Aadhaar lookup, anywhere.** No such API exists, Section 57 of the Aadhaar Act (private
   use of Aadhaar auth) was struck down by the Supreme Court in 2018, and Section 38 makes unauthorised
   access to the identity database a criminal offence. Identity resolution runs on **vehicle number
   plates (ANPR) only**; everything else becomes an "unidentified case."
2. **No server-issued fines.** Only an authenticated municipal officer, after reviewing evidence, can
   confirm a case into a challan. This is enforced in the data model, not just the UI.
3. **Corruption reports never reach the accused's own department/station.** Routing is a configurable
   table (see `backend/app/models/module2_corruption.py`), not a hardcoded "notify nearest station."
4. **No public feed of raw assault/crime footage, ever** — see Module 4's design notes. Evidence goes
   to investigators under chain of custody; what's public is aggregate/delayed/gated instead.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python), SQLAlchemy 2.0, Alembic |
| DB | PostgreSQL 16 + PostGIS |
| Object storage | MinIO (S3-compatible) |
| Queue | Redis (wired for future async CV/notification jobs) |
| Frontend | React + Vite + TypeScript + Tailwind CSS, Leaflet/OSM for maps |
| Auth | JWT, officials only — citizens never create an account |

## Local development

Requires Docker Desktop, Python 3.10+, Node 20+.

```bash
# 1. Start Postgres+PostGIS, MinIO, Redis
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
alembic upgrade head
python -m app.seed.seed_data      # synthetic wards, officials, sample issues
uvicorn app.main:app --reload --port 8000 --no-access-log

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Backend API docs: http://localhost:8000/docs
Frontend: http://localhost:5173
MinIO console: http://localhost:9001 (user/pass in `.env`)

Postgres is published on **host port 5433**, not 5432, because a locally-installed Postgres
commonly already holds 5432 — if the app can't authenticate as `civic`, you're almost certainly
talking to a different Postgres.

### Demo accounts

All synthetic, password `DevPassword123!`: `admin@demo.city`, `officer.roads@demo.city`
(municipal officer), `engineer.sanitation@demo.city`, `moderator@demo.city`,
`vigilance@demo.city`, `investigator@demo.city`.

### Smoke test / demo script

With the stack running and freshly seeded:

```bash
cd backend && python -m tests.smoke_test
```

46 checks covering the guarantees that actually matter — EXIF stripping verified on the stored
photo, GPS/device tags and audio verified gone from the stored video, 50m duplicate clustering, role separation (moderator refused Module 1, municipal officer
refused Module 2), proof-gated resolution, SLA breach + shareable card, officer-confirmed
challans with the fine ladder read from config, appeal separation of duties, and the
police-personnel routing rule that must never notify local police.

It's safe to re-run without resetting — it picks a fresh map location each time so it never
collides with its own earlier data, and skips the challan flow if a previous run already
confirmed the one seeded ANPR case (42 passed / 1 skipped instead of 46). For the full set,
reset first:

```bash
alembic downgrade base && alembic upgrade head && python -m app.seed.seed_data
```

## Repo layout

```
backend/app/
  models/       SQLAlchemy models, one file per module. Each table documents the personal
                data it holds and its retention period in a docstring, per the spec's
                "privacy by design" requirement.
  schemas/      Pydantic request/response schemas
  routers/      FastAPI routers
  services/     jurisdiction resolution (PostGIS), media pipeline (metadata strip, photo
                face blur, thumbnailing), storage (S3/MinIO client), SLA timers, auth
  seed/         synthetic seed data generator
frontend/src/
  pages/        citizen report flow, public status board, officer dashboard, auth
  components/
  lib/          API client, map helpers
```

## Data model notes

- **Audit log is append-only** at the database level (no UPDATE/DELETE grant for the app role in
  production; enforced via a trigger in the migration for this dev build).
- **Role separation** (moderator / municipal officer / vigilance officer / department engineer /
  investigating officer / admin) is modeled in `users.role` and checked in route dependencies. The
  spec calls for storage-policy-level separation for Module 4 evidence specifically — not yet built,
  flagged in the Module 4 stub.
- **SLA config and fine ladders live in DB tables, not code**, per the spec's explicit requirement
  that penalty amounts and deadlines are municipal by-law decisions, not constants.
- **Run uvicorn with `--no-access-log`.** Modules 2 and 4 require that the uploader's IP is never
  persisted anywhere, including logs. Uvicorn's default access log records the client IP for every
  request, which would silently violate that. There's no per-route way to suppress it, so it's
  disabled server-wide. If you add a reverse proxy in front of this in a real deployment, make sure
  its access logs exclude `/api/corruption/*` too.

## Known gaps and things not yet verified

Listed explicitly because several of these look done from the outside and are not.

- **Videos are not face-blurred — a deliberate deviation from the spec.** The spec requires
  faces in stored video to be blurred for Modules 1–3. Blurring every frame took 25–45s per
  10-second clip, so video blur was removed for speed. Location data, device make/model and
  audio are still stripped from every video (stream copy via a bundled ffmpeg, 0.2–0.9s
  measured), and that is what keeps a report anonymous. The consequences: Module 3 videos on the
  public board show bystanders' faces; on Module 2's public corruption feed, pre-publication
  moderation is now the only check for identifiable bystanders in video; Module 1 evidence
  clips reach officers unblurred. Photos are still blurred.
- **Photo face blurring is untested against real faces.** The pipeline runs and blurs what the
  detector finds, but it uses OpenCV's Haar cascade frontal-face detector, which misses profile
  views, partial occlusion, small/distant faces, and performs unevenly across lighting and skin
  tones. It has only been exercised here on synthetic images containing no faces. Before this
  handles anything real, swap in a proper detector behind `_blur_faces_in_frame()` and evaluate
  it on a representative test set. Treat the current blur as a placeholder, not a privacy
  guarantee.
- **The UI has not been opened in a browser.** It typechecks, builds clean (88 modules, ~109 KB
  gzipped) and every module transforms without error, and the API underneath is covered by the
  smoke test — but no one has actually clicked through the report flow, the map, or the officer
  dashboard. Do that before demoing.
- **Virus scanning is a no-op stub** (`virus_scan()` in `services/media_pipeline.py`).
- **Uploads are processed inside the request**: about 2s for a browser-compressed photo (face
  detection) and under a second for most videos. A video whose codec can't be stream-copied into
  MP4 (e.g. ProRes) is re-encoded instead, which takes longer. The upload endpoints are plain
  `def` so FastAPI runs them in worker threads (API stays responsive; measured `/health` at
  ≤0.4s during an upload, versus frozen for the full duration when they were `async def`), and
  the form shows a processing state with a timeout instead of hanging. The spec's intended design
  is to hand the file to a Redis-backed worker and return immediately; that isn't built.
- **The SLA sweep is lazy**, triggered when the public board or officer queue is read, rather
  than running on a schedule. Redis is in the compose file for a Celery/RQ worker that doesn't
  exist yet. Escalation to the tier-2 department on breach is recorded in config but not
  actually dispatched.
- **Notifications only log to the console.** The gateway abstraction is real; no provider is
  wired to it.
- **Module 3 phone opt-in keeps only the first subscriber** per issue, since `contact_token` is
  1:1 with the issue. Ten people reporting one pothole means one of them gets SMS updates.
- **Hindi and Kannada strings are a first pass** and need a fluent-speaker review.
- **WCAG AA is designed for, not audited.** Labels, focus rings, `aria-*` attributes, a skip
  link and a keyboard-accessible alternative to the map pin are all in place; no assistive-tech
  testing or contrast audit has been run.
- Module 1's repeat-offence escalation counts prior confirmed cases for the same plate, but
  since no ANPR runs, no case ever has a plate unless it came from seed data.

## Legal disclaimer

This is a hackathon/portfolio build on synthetic data. See the spec's Appendix A.1 for the statutes
and cases that shaped these decisions (Aadhaar Act, DPDP Act 2023, IT Rules 2021, BNS 72, POCSO, IT
Act 67/67A/67B, *Lalita Kumari*, *Nipun Saxena*, *Tehseen Poonawalla*). None of this is legal advice;
confirm current law before any real deployment.
