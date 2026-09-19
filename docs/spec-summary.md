# Build specification summary

Condensed from the project's build spec. This is the engineering reference used while building;
the full document (with legal citations and demo-day Q&A) should be kept alongside it — ask
whoever owns the original PDF for a copy if you don't have one.

## Substitutions (why the design differs from the "obvious" pitch)

| Original idea | What's built instead | Why |
|---|---|---|
| Face recognition → Aadhaar number | ANPR → vehicle registry; everything else is an "unidentified case" | No reverse-lookup API exists; Aadhaar Act s.57 struck down (Puttaswamy 2018); s.38 makes unauthorised DB access an offence |
| Server auto-generates challan | Officer review queue → confirm/reclassify/dismiss → official challan | Only an empowered officer can issue a valid challan |
| Notify nearest police station of corruption | Route via configurable table to Lokayukta / ACB / CVC / Vigilance Officer | Conflict of interest; endangers the whistleblower |
| Open public feed of accusations | Moderated feed, status badges, right of reply | Defamation exposure; IT Rules 2021 intermediary duties |
| Auto-tag MLA/police social accounts | Official grievance channel + shareable card for citizen to post | Auto-posting = spam, revokes API access, creates no record |
| Public feed of assault/murder/narcotics footage | Sealed evidence vault, station response ledger, hotspot map (quarterly lag), case record after chargesheet | BNS 72, IT Act 67A/67B, POCSO; tips off networks; destroys ID-parade evidence; mob-violence risk |
| Blur victim, then publish | Blur at ingestion, never publish regardless | BNS 72 covers *any matter* revealing identity, not just the face |

## Module 1 — Violation detection & enforcement assist

- Pipeline: ingest (RTSP or file) → YOLOv8 detection → identity resolution (ANPR or unidentified
  case) → officer review queue → challan generation on confirm → repeat-offence escalation → appeals.
- Faces auto-blurred before storage; unblur is officer-only, audit-logged.
- Fine ladder lives in a config table (Rs 500 first offence, Rs 1,000 second+, per 12-month rolling
  window) — never hard-coded.
- Violation classes: littering, illegal dumping, spitting, public urination/defecation, vandalism,
  illegal posters, open burning, footpath encroachment, illegal parking, waste-spilling vehicles,
  tree damage, smoking in no-smoking zones.

## Module 2 — Anonymous corruption reporting

- No account, no login, no phone/email, no IP logging on the endpoint, EXIF stripped, coarse
  user-chosen geohash, bystander auto-blur + manual blur, audio muting, one-time random tracking
  token.
- Routing table (accused party → primary route → local police notified):
  - State govt employee → State Lokayukta/ACB → yes, after moderation
  - Central govt employee → CVC → yes, after moderation
  - Police personnel → State ACB + Police Complaints Authority → **never**
  - Municipal/dept staff → District Vigilance Officer → yes, after moderation
- Public feed: moderation queue before visibility, status badges (Unverified / Under Investigation /
  Action Taken / Dismissed), never names the accused individual (department + designation only),
  Grievance Officer + takedown + right of reply per IT Rules 2021, device-level rate limiting.

## Module 3 — Civic infrastructure reporting (built)

- Categories + default SLA + escalation target: traffic signal (24h → traffic police → DCP), water
  leak (24h → water board), fallen tree (24h → ward officer → commissioner), street light (72h →
  electrical dept), blocked drain (72h → sanitation → health officer), uncollected garbage (72h →
  sanitation inspector), pothole (7d → roads engineer → MLA office), damaged footpath (14d → roads
  engineer), broken public toilet (7d → sanitation → health officer), damaged bus stop (14d →
  transport corp), illegal hoarding (7d → town planning → commissioner), stray cattle (48h → animal
  husbandry → ward officer).
- Flow: upload (photo/video + category + map pin, anonymous by default, optional phone in a
  separate table) → metadata strip + blur (shared pipeline) → PostGIS jurisdiction resolution (ward,
  zone, constituency) → notify responsible desk → SLA timer → public status board → duplicate
  clustering (50m radius, same category → merge + upvote).
- No auto-posting to officials' social media — generates a shareable card for citizen-initiated
  escalation instead.

## Module 4 — Emergency incident reporting & evidence custody (not built yet)

- Triage screen before any camera: Tier A (in progress / life at risk) → one-tap 112 call with
  location, silent-alarm mode, evidence capture offered only after help dispatched. Tier B (already
  occurred / ongoing) → evidence capture with chain of custody.
- **Any offence involving a minor is a hard stop — refuse the upload entirely**, redirect to 1098 /
  112 / CCPWC. Do not store it "to forward it later."
- Evidence pipeline: client-side SHA-256 hash before processing → dedicated evidence vault (separate
  bucket/policy/retention/encryption key from Modules 1–3) → minimal server record (hash, time,
  geohash, category — never IP/account/device ID) → append-only chain-of-custody log → alert
  dispatch (never includes the video itself) → one-time tracking token.
- Sexual-offence reports: irreversible blur at ingestion, `restricted` flag enforced as a **DB
  constraint** (no role, including admin, can unset it), immediate support resources (181, 112,
  nearest One Stop Centre, 1098 if a minor), suppressed from all public surfaces including
  ward-level aggregates below a k-anonymity threshold of 5.
- Access control: only an investigating officer with a case/FIR number can view evidence; every view
  logged; **moderators have zero access to Module 4 data** — this needs to be enforced at the
  storage-policy layer, not just application code.
- Transparency layer (what's public instead of footage): station response ledger (received,
  unacknowledged-past-SLA counter, FIRs registered + conversion rate, median ack time, cases past
  statutory timelines, closures without FIR + reason code), automatic time-driven escalation ladder
  (1h/24h/7d/30d triggers → district control room → SP/DCP → Police Complaints Authority → State
  Human Rights Commission), aggregate hotspot map (per ward per quarter, quarterly lag, k-anonymity
  ≥5, never live), case record that only opens at chargesheet (nothing case-specific before that;
  sexual-offence/minor categories never disclosed at any stage).

## Cross-cutting

- **Shared video ingestion pipeline** (Modules 1–3): upload → virus scan → EXIF/metadata strip →
  face detect + blur (irreversible on stored copy) → transcode → thumbnail/keyframe extraction →
  object storage, returns opaque media ID.
- Module 4 differs: hash *before* processing (chain of custody), blur still irreversible, writes to
  the evidence vault, not general storage.
- Privacy-by-design: every table's personal-data contents and retention period documented next to
  its definition. Module 1 evidence deleted once challan paid or appeal window closes. Modules 2/3
  hold no uploader identifiers by default. Module 3's optional phone number lives in a separate
  table joined by a one-way token, purged on resolution. Module 4 on a documented legal retention
  schedule, own encryption key, never enters general storage or any public surface.
- Full append-only audit log for every official action (view/confirm/dismiss + timestamp).
- Role-based access, least privilege: municipal officer, vigilance officer, moderator, department
  engineer, investigating officer, admin. A moderator can't see Module 1 identity data; a municipal
  officer can't see Module 2 reports; only an investigating officer with a case number sees Module 4.
- WCAG AA, Hindi + one regional language selectable without an account, must work on a low-end
  Android phone over 3G with client-side compression.

## Suggested build order (from the spec)

1. Shared video service, storage, auth, schema
2. Module 3 (infrastructure reporting) — simplest, proves the pipeline end to end
3. Module 2 (corruption reporting + feed) — reuses Module 3's upload flow
4. Module 1 (detection + enforcement) — highest risk, YOLOv8/ANPR tuning
5. Module 4 (evidence vault + transparency layer)
6. Officer dashboard, audit log, escalation timers
7. Seed data, demo script, README
