# Civic Accountability Platform

A four-module civic accountability platform for Indian municipal jurisdictions, built from the
project's build specification (see [`docs/spec-summary.md`](docs/spec-summary.md)). Synthetic data
only, no live government API integration, no real personal data.

> Draft engineering project. Not legal advice. See the spec's Appendix for the legal reasoning
> behind the design choices called out below.

A scripted walkthrough for presenting it is in [`docs/DEMO.md`](docs/DEMO.md).

## What's built

All four modules are implemented, each with a citizen-facing flow and an officer-side view.

| Module | Status |
|---|---|
| Shared plumbing (auth, DB, PostGIS jurisdictions, audit log, storage, media pipeline) | Built |
| Module 3 — Civic infrastructure reporting | Built end to end |
| Module 1 — Violation detection & enforcement assist | Built end to end, **except the CV pipeline**: there is no YOLOv8 detection and no ANPR/OCR, so cases arrive from citizen uploads or seed data and ANPR-path cases have no plate resolved until an officer supplies one. Officer review, challan issuance off a config-driven fine ladder, disputes and second-officer appeals all work. |
| Module 2 — Anonymous corruption reporting | Built end to end: anonymous upload with browser-side coarse geohashing, routing-rules table, pre-publication moderation, public feed with status badges, tracking tokens, device-fingerprint rate limiting, and the IT Rules 2021 grievance channel — published Grievance Officer, 24-hour acknowledgement and 15-day disposal clocks, takedown on an upheld grievance, moderated right of reply published under the allegation, and the platform's own compliance figures. **Not built:** uploader-driven extra blur regions, audio muting. |
| Police station section | Built: station network with locations and nearest-station routing, General Diary, FIR register with station-issued numbers, Zero FIR transfer, case diary, chargesheet and closure — see below. |
| Module 4 — Emergency reporting & evidence custody | Built: triage screen that leads with a 112 call, hard stop for any offence involving a minor, sealed evidence vault with chain of custody, case-number-gated investigating-officer access, and the public transparency layer (station response ledger, aggregate hotspot map, and a stage-gated case record that opens at chargesheet). **Not built:** storage-policy-level separation at the bucket layer, per-report encryption keys, auto-purge on a retention schedule, and the irreversible video blur that restricted categories would need (video is refused there instead). |

### The grievance channel, takedown and right of reply

A moderated feed of accusations makes this an intermediary, and Rule 3(2) of the IT Rules 2021
attaches duties to that: publish a Grievance Officer, acknowledge a complaint within 24 hours,
dispose of it within 15 days. All three are implemented, and the deadlines are columns rather
than prose.

The design turns on one thing: **a takedown is the only power here that makes a citizen's report
disappear, so using it leaves marks in four places at once.**

| Who | What they can see |
|---|---|
| The complainant | A numeric ticket, the status, the deadline, and the reason for the decision |
| The anonymous uploader | That their report was withdrawn, and on what ground, through their tracking token |
| The public | Counts of grievances received, deadlines missed, and how many were upheld |
| An auditor | `audit_log` rows with `action = 'TAKEDOWN'`, naming the officer, on an append-only table |

Two further choices worth naming:

- **A reply is offered before removal is.** The response page leads with "publish a reply", which
  leaves the report standing and shows the reader both sides, and offers removal second. Offering
  only removal would make deletion the sole available answer to criticism.
- **A reply is published as the office, never as the person.** The responding official's name and
  email are collected so a moderator can verify the reply is genuine, and neither is ever
  published. Module 2 never names the accused individual; publishing the name of the officer who
  replies to an allegation about a single-post designation would name them by the back door.

The acknowledgement is sent when the grievance is filed, not when an officer gets to it. If the
mail gateway is down the row stays unacknowledged and the missed deadline shows up in the public
figures, rather than being papered over with a timestamp for a mail that never went out.

### The police station section

Module 4 routes a report to a station; this is what the station then does with it. The chain
mirrors a real station's, because the public response ledger only means anything if the record it
measures is the one the station actually keeps.

    report routed to the nearest station
        -> General Diary entry on arrival
        -> acknowledged by the duty officer
        -> FIR registered (BNSS s.173), or closed with a stated reason
        -> investigating officer assigned
        -> case diary entries as the investigation runs (BNSS s.192)
        -> chargesheet filed, or a closure report

- **Six stations across four wards**, each mapped to a location. Two wards hold two stations, so
  a report routes to the **nearest** station rather than assuming one ward means one station. The
  public directory at `/stations` answers "which station covers this spot" the same way.
- **The General Diary** (Roznamcha, Police Act s.44) is written by every procedure, in the same
  transaction as the action itself, numbered per station per day. A station cannot act here
  without it appearing in its diary.
- **FIR numbers are issued by the station in sequence** (`0042/2026`), never typed in, so the
  register cannot be back-dated or have gaps inserted.
- **Zero FIR** is a procedure, not a refusal: a station registers even when the offence is outside
  its jurisdiction and transfers the investigation. The registration stays where it was made.
- **The General Diary and case diary are append-only at the database level** — UPDATE, DELETE and
  TRUNCATE are all rejected, the way a bound register behaves.
- **An officer is posted to a station** and sees only that station's reports, FIRs and diary. The
  one exception is a transferred Zero FIR, which both the registering and receiving stations can
  work.
- **The public ledger counts FIRs from this register**, so "FIRs registered" means the station
  actually registered one — not that a field was filled in somewhere.

### If you touch Module 4

These are the parts that must not be loosened, and each is enforced rather than documented:

- **The hard stop for any offence involving a minor** happens before a single byte is read.
  Accepting that upload "to forward it" is itself an offence under POCSO and IT Act 67B.
- **Evidence lives in a separate vault bucket**, never the media bucket the public pages read.
- **Only an investigating officer supplying a case or FIR number** can open evidence, and every
  open appends to an append-only chain of custody. Moderators get 403 on every route here.
- **Sexual-offence and minor categories never reach a public surface**, including aggregate
  counts — `PUBLIC_CATEGORIES` in `services/transparency.py` is the allowlist that enforces it.
- **The hotspot map runs a quarter behind with a k-anonymity threshold of five.** A live map is
  an intelligence feed for the people being reported, and a cell of one points at whoever filed it.

Still missing before this could be deployed: separation enforced by bucket policy rather than
application code, per-report encryption keys, and the auto-purge schedule.

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

**Restart the Vite dev server after editing `tailwind.config.js`.** Tailwind reads its config
once at startup, so a theme value added while the server is running produces a "class does not
exist" error in the browser even though `npm run build` succeeds from a fresh process.

Postgres is published on **host port 5433**, not 5432, because a locally-installed Postgres
commonly already holds 5432 — if the app can't authenticate as `civic`, you're almost certainly
talking to a different Postgres.

### Demo accounts

All synthetic, password `DevPassword123!`: `admin@demo.city`, `officer.roads@demo.city`
(municipal officer), `engineer.sanitation@demo.city`, `moderator@demo.city`,
`vigilance@demo.city`, `investigator@demo.city` (posted to Riverside station).

Station staff, for the police station section: `sho.lakeview@demo.city`, `sho.market@demo.city`
and `io.riverside@demo.city` — each posted to a different station, so logging in as two of them
shows the scoping.

### Smoke test / demo script

With the stack running and freshly seeded:

```bash
cd backend && python -m tests.smoke_test
```

148 checks covering the guarantees that actually matter, across all four modules: EXIF
stripping verified on the stored photo, GPS/device tags and audio verified gone from the stored
video, 50m duplicate clustering, proof-gated resolution, SLA breach + shareable card,
officer-confirmed challans with the fine ladder read from config, appeal separation of duties,
the police-personnel routing rule that must never notify local police, a corruption report that
stays off the feed until moderated, the hard stop on any offence involving a minor, evidence
refused without a case number and served only from the vault bucket, a hotspot map that
suppresses cells below five and never carries a restricted category, the station procedure
chain from acknowledgement through FIR to chargesheet with a General Diary line for each step,
and a case record that discloses the court only once a chargesheet is filed.

The grievance checks assert the awkward cases rather than the happy path: a complaint about an
unpublished report is a 404 and not a 403 that would confirm the report exists, a ticket lookup
returns neither the complainant nor the complaint text, a published reply carries the office but
not the official who wrote it, an upheld grievance both removes the report and tells the
anonymous uploader why, and the takedown is read back out of `audit_log` in PostgreSQL rather
than taken on the API's word.

Role separation is asserted in both directions: a moderator is refused Module 1 identity data
and every Module 4 route, and a municipal officer is refused Module 2 reports.

It's safe to re-run without resetting — it picks a fresh map location each time so it never
collides with its own earlier data, and skips the challan flow if a previous run already
confirmed the one seeded ANPR case (144 passed / 1 skipped instead of 148). For the full set,
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
                face blur, thumbnailing), storage (S3/MinIO), evidence vault (Module 4,
                separate bucket), station (nearest-station routing, General Diary,
                FIR numbering), transparency (ledger + k-anonymous hotspots), SLA
                timers, tracking codes, notifications, auth
  seed/         synthetic seed data generator
frontend/src/
  pages/        one flow per module: infrastructure report + board + tracking,
                corruption report + moderated feed, violation report, emergency
                triage, public transparency layer, officer dashboard, auth
  components/   shared UI, plus components/officer/* — one panel per module, shown
                only to the roles the API would accept
  lib/          API client (upload progress, timeouts), coarse geohashing, i18n
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
- **Module 3 tracking codes are 10 digits; Module 2 and 4 tokens are not.** A citizen reads a
  Module 3 code off a screen and types it back, and it is printed on the public status board
  anyway, so it is a lookup handle rather than a credential — it reveals nothing that
  `GET /api/infra/issues/{id}` doesn't already return to anyone. Module 2 and Module 4 keep
  high-entropy random tokens, because there the token is the reporter's only protection and a
  guessable one would let anyone enumerate whistleblower reports. Don't unify these.
- **Run uvicorn with `--no-access-log`.** Modules 2 and 4 require that the uploader's IP is never
  persisted anywhere, including logs. Uvicorn's default access log records the client IP for every
  request, which would silently violate that. There's no per-route way to suppress it, so it's
  disabled server-wide. If you add a reverse proxy in front of this in a real deployment, make sure
  its access logs exclude `/api/corruption/*` too.

## Security

Dependencies are checked with `pip-audit` (backend) and `npm audit` (frontend); both report zero
known vulnerabilities as of the last pass. Re-run them before any deployment — the biggest risk
in a project like this is not an exotic bug, it is shipping a months-old image parser.

```bash
cd backend && python -m pip_audit
cd frontend && npm audit
```

What is enforced in code:

- **Startup refuses an insecure production config.** With `ENV` set to anything but
  `development`, the app will not boot on the default or a short `JWT_SECRET`, or on a wildcard
  CORS origin. A deployment that forgot to set a secret would otherwise look perfectly healthy
  while anyone who read this repo could sign a token as admin.
- **API docs and the OpenAPI schema are served only in development.** They are a route inventory.
- **Uploads are size-capped and read in chunks** (`MAX_IMAGE_UPLOAD_MB`, `MAX_VIDEO_UPLOAD_MB`).
  Every upload route processes the file in memory, so an unbounded read is a one-request denial
  of service.
- **Rate limits** on login (brute force) and on every anonymous submission route. The limiter
  never stores an IP: the key is a hash of IP + user agent + a salt generated at process start,
  kept in memory only, because Modules 2 and 4 promise the uploader's IP is never persisted and a
  rate-limit table keyed by IP would quietly be exactly that. Counters are per-process, so a real
  deployment should also rate-limit at the gateway.
- **Security headers** on every API response: `nosniff`, `DENY` framing, no referrer, a
  `default-src 'none'` CSP, `no-store`, and HSTS outside development. The frontend is served from
  a different origin and needs its own.
- **Coordinates are bounds-checked** before they reach PostGIS, and the media route only accepts
  keys matching the pattern this service generates — it cannot be used to probe for other objects
  or to smuggle traversal sequences.
- **JWTs** are verified with an explicit algorithm allowlist, so neither `alg: none` nor a token
  signed with a different algorithm is accepted. Tokens expire in an hour.
- **Investigating officers are scoped to their jurisdiction** for Module 4 queues and evidence.
- **Seeding refuses to run outside development** — the demo accounts share a password printed in
  this file.

Known weaknesses, not yet addressed:

- **The officer token lives in `localStorage`**, so any successful XSS on the frontend can take
  it. httpOnly cookies plus CSRF protection would be the fix.
- **No account lockout or second factor** for officials; rate limiting is the only brute-force
  control.
- **Module 4's separation is enforced in application code**, not by bucket policy or per-report
  encryption keys.
- Everything runs over plain HTTP locally. TLS termination is assumed to be in front.

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
- **The UI has not been opened in a browser.** It typechecks, builds clean (101 modules, 144 KB
  gzipped JS + 5.5 KB gzipped CSS) and every module transforms without error; the dev server's
  compiled stylesheet has been fetched and checked for PostCSS errors, and the API underneath is
  covered by the smoke test — but no one has actually clicked through the report flow, the map,
  or the officer dashboard. Do that before demoing.
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
- **Web fonts load from Google Fonts** (Inter, plus Noto Sans Devanagari and Kannada for the
  Hindi and Kannada UI). A deployment that cannot reach them falls back to the system font
  stack; self-host the files if that matters.
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
