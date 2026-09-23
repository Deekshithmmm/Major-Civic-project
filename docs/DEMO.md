# Demo script

A twelve-minute walkthrough that shows the whole system and, more importantly, shows *why* it is
built this way. Every refusal below is deliberate — they are the parts worth demonstrating.

## Before you start

```bash
docker compose up -d
cd backend
alembic upgrade head
python -m app.seed.seed_data          # prints the tracking codes you will need
uvicorn app.main:app --port 8000 --no-access-log
# separate terminal
cd frontend && npm run dev
```

Keep the seed output on screen — it prints the demo accounts and the tracking codes.

All accounts use the password `DevPassword123!`.

---

## 1. The problem, in one screen (1 min)

Open **http://localhost:5173**.

The home page lists every report the public is allowed to see, with its photo or video. Point at
the counter row, specifically **"Crime reports unacknowledged past deadline"**.

> That number is the product. Everything else supports it.

Scroll to **"What is deliberately not shown here"**. Two things are missing on purpose: violation
evidence, because until an officer confirms it, it is an unproven accusation against an
identifiable person; and crime footage, at any stage.

## 2. Reporting a pothole (2 min)

**Civic infrastructure → Report an issue.**

- Pick a category, drop a pin, attach a photo, submit.
- Note the upload bar, then **"Processing…"** — the server is stripping location data.
- You get a **10-digit tracking code**. Say plainly: it is tied to no identity, no account, no
  phone number. Nothing else can look it up.
- Submit the *same* category at the *same* spot again → *"Someone already reported this nearby."*
  Ten people reporting one pothole produce one prioritised ticket, not ten ignored ones.

**Track a report** → paste the code with spaces. It still resolves.

## 3. The officer side, and the proof requirement (1 min)

**Officer login** → `officer.roads@demo.city`.

- Acknowledge the report.
- Try **Resolve** without attaching a photo → rejected. An officer cannot mark something fixed
  with no evidence that it was.
- Attach one → resolved, and the proof photo is now public on the issue page.

Filter the board by **Overdue** → the seeded breached report, and its **shareable card**. The
platform never posts on anyone's behalf; it prepares the text and the citizen decides.

## 4. Corruption, and who gets told (2 min)

**Corruption → Report corruption anonymously.**

Change **"Who is being reported"** to **Police personnel** and pause on the line that appears:

> *Local police are never notified about reports against police personnel.*

That is the single most dangerous failure mode in the original concept — notifying the accused's
own station that someone reported them. Routing goes to the State ACB and the Police Complaints
Authority instead.

Pick a point on the map and show the saved value: a **geohash covering roughly a kilometre**, not
the exact spot. An over-precise location points at whoever filmed.

Submit, then log in as `moderator@demo.city` → **Moderation**. Nothing reaches the feed until a
moderator approves it. Approve it, and note the badge: **Unverified allegation**. The platform
never names an individual — department and designation only.

## 5. When the platform gets it wrong (2 min)

This is the section that answers the obvious objection: *you have built a machine for publishing
accusations — what happens to the person it is wrong about?*

Stay on the feed. The seeded **Roads & Works Department** report already carries a **response from
the office named**, quoted under the allegation. The reader sees the accusation and the answer in
the same place. Note the attribution: the *Executive Engineer*, not a person. The official who
wrote it gave their name and work email so a moderator could verify the reply was genuine, and
neither is published.

Click **Reply or object**. Two tabs, in this order deliberately:

- **Publish a reply** — the report stays up, the answer goes underneath it.
- **Ask for removal** — the grievance channel.

Offering only the second would make deletion the only available response to criticism.

Open **Grievance Officer** (also linked from the footer of every page). Rule 3(2)(a) of the IT
Rules 2021 requires this page to exist: a named officer, an address, and two deadlines —
**acknowledge within 24 hours, decide within 15 days**. Scroll to **Our own record**: the same
counters this platform points at a police station, pointed at itself.

File a grievance. You get an **8-digit ticket** and the acknowledgement goes out immediately —
not when an officer gets round to it, because the 24 hours start the moment it is filed.

Look up the ticket. It shows the status, the deadline and the decision. It does **not** show the
complaint text or the complainant's details, so guessing a ticket number harvests nothing.

Now log in as `moderator@demo.city` → **Grievances**, and uphold it. Then show what one takedown
left behind:

| Where | What |
|---|---|
| The feed | The report is gone |
| The uploader's tracking code | "Withdrawn", and the reason why |
| The compliance figures | Upheld: 1 |
| `audit_log` in psql | A `TAKEDOWN` row naming the moderator, on a table that rejects UPDATE, DELETE and TRUNCATE |

The line to say out loud: **the power to remove a citizen's report is the most dangerous thing in
this system, so it is the most heavily recorded.** Nobody can use it quietly.

## 6. The hard stop (1 min)

**Emergency.**

The first screen is triage, not a camera. Choose **"Someone is in danger right now"** → a one-tap
**112** call. Evidence capture is offered only afterwards. An app that opens into a camera teaches
bystanders to film an assault instead of calling for help.

Go back, choose the second option, and set the category to **"Anything involving a child under 18"**.

The upload field disappears and is replaced by 1098, 112 and the CCPWC portal. Try it against the
API too — the server refuses with a file attached. Accepting that upload, even to forward it, is
itself an offence under POCSO and IT Act 67B.

## 7. What replaces the video feed (2 min)

**Accountability.**

- **Station response ledger.** One station is flagged red — a report past seven days with no FIR.
  Under *Lalita Kumari* (2014) registering an FIR is mandatory where the information discloses a
  cognizable offence, so a low conversion rate is a legal question, not an opinion.
- **Hotspot map.** One cell is shown. A ward with three reports in the same quarter is *absent* —
  suppressed below the threshold of five — and the map runs a quarter behind. A live map of
  narcotics reports is an intelligence feed for the people being reported.
- **Case record.** Stage-gated: before a chargesheet nothing case-specific, after it the sections
  and the court, because proceedings are public from that point anyway.

> A station sitting on twenty reports with zero FIRs is visible to every citizen and journalist
> within a day, and the case is still prosecutable because nothing was published that the defence
> can use.

## 8. Inside the police station (2 min)

**Police stations** → click one. Contact details, location, and how it responds to what it
receives.

Log in as `sho.lakeview@demo.city` → **Police station** tab.

- Take a fresh report: **Acknowledge**, then enter sections and **Register FIR**. The number is
  issued by the station in sequence — it is not typed in.
- Add a **case diary** entry, then **file a chargesheet**.
- Open the **General Diary** tab: every one of those steps wrote a numbered line, and they cannot
  be edited or deleted — the database refuses it.
- Show a **Zero FIR** in the FIR register: registered at Market East, transferred to Market. A
  station must register even when the offence is outside its jurisdiction.

Log in as `sho.market@demo.city` to show the scoping: a different station, a different queue.

## 9. If a reviewer pushes (closing)

Run the smoke test on screen:

```bash
cd backend && python -m tests.smoke_test
```

148 checks. It does not assert that buttons work — it asserts the guarantees: GPS metadata
verified gone from the stored file, a moderator refused Module 4 on every route, evidence refused
without a case number, the hotspot map suppressing small cells, and a takedown that cannot happen
without leaving a row in an append-only audit table.

Then, in `psql`, try to tamper with the record:

```sql
UPDATE audit_log SET detail = 'x';
DELETE FROM station_diary_entries;
UPDATE emergency_reports SET is_restricted = false WHERE is_restricted = true;
```

All three are refused by the database, not by application code.

---

## Questions worth pre-empting

**"Why not face recognition to Aadhaar?"** No reverse-lookup API exists, Section 57 was struck
down in 2018, and Section 38 makes unauthorised database access an offence. Identity resolves by
number plate, which is how e-challan already works.

**"Who issues the fine?"** An authenticated officer, after reviewing the evidence. The system
builds the case; anything else is legally void.

**"Why isn't the assault footage public?"** BNS 72 criminalises publishing any matter revealing a
sexual offence victim's identity; blurring is not a defence because location, clothing and
bystanders survive it. Publication also taints identification evidence and warns the network. The
ledger delivers the accountability instead, and faster.

**"What stops police ignoring a report?"** The unacknowledged counter, per station, public within
a day — and it is computed from timestamps, so no one decides whether a report was ignored.
