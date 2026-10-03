# StreamSaathi Guardians

**Points come from being right, not from posting more — and every game round is also quality control.**

`OneAquaHealth IEEE Global Hackathon 2026` · Primary: **Track 5, Community & Gamification** · Secondary: **Track 3, AI-Supported Assessment** · Team **0xalgos**

> Live demo: _add Vercel URL_ · API docs: _add Render URL_`/docs` · Demo video: _add link_

---

## The problem

Citizen stream monitoring has a volume problem and a trust problem, and they pull against each other.

**Track 5 (community):** volunteers sign up, submit two or three reports, and stop. Classic gamification makes this worse — reward submissions and you get more submissions, not better ones. Leaderboards make it worse again, because only the top few feel like winning is possible.

**Track 3 (assessment):** researchers can't use what arrives. Terms are ambiguous ("is this channel *partly* reshaped?"), photos are blurry, GPS drifts, and nobody can tell a careful observer from a hurried one. So the data needs expert review — and expert time is the scarcest thing in the whole system.

StreamSaathi Guardians treats these as one problem. The mechanic that keeps volunteers coming back is the same mechanic that makes the data trustworthy: **people check each other's photos.** Engagement and quality control stop competing for attention.

---

## How it works

1. **Join and practise.** A new volunteer scores 4 photos whose correct answers an expert already knows, and immediately sees how they did: *"You matched the expert on 3 of 4."* They learn the scale before touching real data, and the app learns how good they are.

2. **Check a stream.** For each indicator: take a photo, give a score, say **how sure you are**, and *then* see the AI's second opinion. The human always answers first. If the two of you disagree by two points or more, a **Disagreement Card** shows what you agree on, where you differ, what the AI can't see, and one plain question from config — then lets you keep your answer, change it, or ask an expert.

3. **Submit.** Points are created **pending**. Nothing is earned yet.

4. **Spot Check.** Other volunteers score your photos *blind* — no submitter, no location, no sight of your answer or the AI's. Practice photos with known answers are mixed in silently to measure each player. When enough qualified players agree, your report becomes **crowd-verified** and your pending points settle. When they disagree, it goes to an expert.

5. **Experts handle only the hard cases.** The review screen shows the crowd's votes as an anonymous histogram and how sure the citizen was. One decision settles everyone's points, writes receipts, and turns wrong answers into lessons. A good verified photo can be promoted into a new practice photo with one click.

6. **See your impact.** Receipts ("your vote caught an error"), a skill map per indicator, personal blind spots, badges for variety, an adopted stream with a monthly streak — and a river that heals as your confirmed work adds up.

---

## Screenshots

| | |
|---|---|
| **Home — the Living River** <br> _add screenshot_ | **Spot Check** <br> _add screenshot_ |
| **Disagreement Card** <br> _add screenshot_ | **Expert review with crowd votes** <br> _add screenshot_ |
| **Profile — skill map and badges** <br> _add screenshot_ | **Stream Station poster** <br> _add screenshot_ |

---

## What makes this different

### 1. Points only for being right

Submitting earns **nothing**. Points are created `pending` and settle only when the crowd or an expert confirms the work. A wrong answer loses nothing — there are no negative points anywhere in the ledger — it becomes a short lesson instead. Levels are gated on accuracy and verified checks, never on volume, and there is **no individual leaderboard**: team goals only.

### 2. Skill-weighted consensus

Not every vote counts the same. Each vote carries a weight derived from that player's accuracy **on that specific indicator**, measured against gold photos. Consensus is a *weighted median*, so one person tapping "5" on everything barely moves it.

The weight is shrunk toward neutral twice — once by per-indicator sample size, once by overall sample size — so a brand new player is exactly neutral and a perfect 4-photo practice round earns 1.6, not 2.0. **Anti-cheat is enforced in three places** (SQL, round building, and again at consensus time, because crew membership can change *after* a vote is cast): never your own photo, never a crew-mate's, never one you already judged, and gold stays indistinguishable from real work in the API response.

### 3. A proof panel instead of a claim

`/insights` answers *"does the game actually make the data better?"* with four measured numbers: how often **one citizen alone** matched the expert, how often **the crowd** did, the same split per indicator, and **what share of observations needed an expert at all**. Both lines are measured on the same expert-scored answers so the comparison is honest, sample size is always shown, and empty data reports `null` rather than `0%`.

### 4. Stream Stations — a printable QR poster per site

Any site can produce an A4 poster: *"StreamSaathi Station #7 — scan, check this stream in 2 minutes."* The page it points at needs **no login**, shows six months of One Health dots and a plain sentence about recent condition, and turns a passer-by into a contributor in two taps. Checks that start at a poster are tagged `source='station'` and show a distinct marker on the map.

### 5. The Living River

Home is an inline animated SVG stream that heals in 8 stages as your **confirmed** work accumulates: litter disappears → water clears brown to blue → fish → frogs → bank plants → trees → birds. It is driven only by verified checks, gold matches and errors caught — config validation *rejects* any stage keyed to anything else — so the caption **"Your river grows only when you're right"** is enforced rather than claimed.

---

## Responsible AI, privacy and fairness

**AI suggests, the human decides.**
- The citizen commits to a score *and* a confidence **before** the AI is called. The order is enforced server-side by the request shape.
- Every AI output is labelled "AI suggestion · you decide". The human's score, the AI's score and the expert's score are stored **side by side** and never overwritten.
- The model is instructed to return `can_assess=false` rather than guess; the UI then says "I can't judge this" and offers Retake / Skip.
- If the AI times out or returns nonsense, the flow continues on the human's answer. The AI can never block a submission.
- The Disagreement Card's clarifying questions come from `indicators.json`, **never generated by the model** — a model that wrote its own cross-examination could lead the citizen toward its own answer.

**Privacy.**
- Spot Check voters never see the submitter, the exact location, the citizen's score, the AI's score, or other people's votes. The response type has no field to put them in, and a test walks the whole JSON asserting 19 forbidden keys are absent.
- Photos live in a private bucket, EXIF (location and device) is stripped on upload, and access is via short-lived signed URLs.
- Public and cross-user surfaces (station pages, site timelines, crowd panels) carry **aggregates only**: counts, levels, and coordinates rounded to ~100 m.
- Emails never appear in any cross-user response.

**Fairness.**
- No negative points, ever. No individual public ranking. Wrong answers produce lessons.
- Everyone may play; skill only gates whether a vote *moves data*, never whether somebody can take part.
- Thresholds, rewards, levels, badges and quests all live in config, so the balance can be argued about and changed without touching code.

**Tamper-evidence.** Every state change on an observation appends to a hash-chained `audit_events` table with an append-only database trigger, so a silent edit is detectable.

---

## Architecture

```
Browser (Next.js 16 on Vercel)
   │  Supabase Auth ──► JWT
   │  every API call: Authorization: Bearer <JWT>
   ▼
FastAPI (Render) ── verifies JWT (JWKS or HS256), checks ownership on every route
   ├── Supabase Postgres  (service key, so each endpoint authorises itself; RLS on as depth)
   ├── Supabase Storage   (private bucket, signed URLs, EXIF stripped)
   └── Vision LLM (Gemini / Groq) behind services/ai_opinion.py
```

**Shape of the code.** Business rules live in **31 service modules** (144 functions) under `backend/app/services/` — no DB, no FastAPI — so they are unit-testable without a database. Routers only orchestrate. All database access goes through one `RepoProtocol`, with a real `SupabaseRepo` and an in-memory `FakeRepo` kept in lockstep, which is why **618 tests run with no database at all**.

- **36 API endpoints**, 19 frontend routes
- **8 config files**: `indicators`, `rules`, `one_health`, `calibration`, `game`, `badges`, `quests`, `river`
- Charts are inline SVG. The only runtime dependencies beyond React and Next are `@supabase/supabase-js`, `leaflet`, `react-leaflet` and `qrcode`.

**Tech:** Next.js 16 (App Router, TypeScript, Tailwind v4, mobile-first) · FastAPI + Pydantic v2 · Supabase (Postgres, Auth, Storage) · Gemini Flash / Groq vision · Vercel + Render · GitHub Actions

---

## Local setup

```bash
# 1. Database: run the migrations below in the Supabase SQL editor, in order.

# 2. Backend
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt && cp .env.example .env        # fill in values
uvicorn app.main:app --reload

# 3. Frontend
cd frontend && npm install && cp .env.example .env.local           # fill in values
npm run dev
```

**Checks:** `cd backend && pytest -q && ruff check .` · `cd frontend && npm run lint && npm run build`

### Migrations — run in this order

| # | File | What it adds |
|---|---|---|
| 001 | `001_init.sql` | profiles, observations, indicator_answers, signup trigger |
| 002 | `002_review_audit.sql` | expert review columns, hash-chained append-only `audit_events` |
| 003 | `003_insight.sql` | micro-lessons, One Health column, seed marker |
| 004 | `004_calibration_heatmap.sql` | calibration timestamp, disagreement view |
| 005 | `005_guardians_core.sql` | human confidence, crowd consensus, sites, gold items, votes, points ledger, receipts, badges |
| 006 | `006_adoptions.sql` | `site_adoptions` (partial unique index on active adoptions) |
| 007 | `007_stations.sql` | `sites.station_number` sequence, `observations.source` |
| 008 | `008_practice_attempts.sql` | `practice_attempts` (XP-only replays) |

Every migration is idempotent — safe to run twice — and every new table has RLS enabled with no policies, because the backend holds the service key and authorises each request itself.

### Demo data

```bash
cd backend
python -m scripts.seed_gold                                    # practice photos from calibration.json
ALLOW_SEED=1 SEED_PASSWORD=<yours> python -m scripts.seed_demo_crowd --full
python -m scripts.seed_demo_crowd --reset-info                 # prints the cleanup SQL
```

The seed leaves the app genuinely alive: 3 qualified players, an expert, 3 sites, 7 observations (crowd-verified, expert-corrected, and one still waiting), an adopted site with a 3-month streak, receipts, badges, practice XP, and non-trivial proof numbers. **Everything runs through the real services** — consensus, points, badges, settlement — so nothing on screen is a hard-coded result. All rows are removable: observations carry `is_seed`, and deleting the `@demo.streamsaathi.app` accounts cascades the rest.

Without a database, `python -m scripts.demo_flow` walks the entire game end-to-end in memory and prints each step.

---

## Demo credentials

| Role | Email | Password |
|---|---|---|
| Citizen | `demo-citizen@demo.streamsaathi.app` | _your `SEED_PASSWORD`_ |
| Guardian (voter) | `demo-player-1@demo.streamsaathi.app` | _your `SEED_PASSWORD`_ |
| Expert | `demo-expert@demo.streamsaathi.app` | _your `SEED_PASSWORD`_ |

---

## Future work

- **Crews UI** — the backend shape and the anti-cheat rule for crew-mates are already in place (`observations.crew_id`, excluded at round building *and* at consensus); the tables, join-by-code flow and team goal screens are not built yet.
- **Offline mode** — a stream bank is exactly where signal fails. Queue a full check locally and sync on reconnect.
- **Hindi voice prompts** — `indicators.json` already carries Hindi help text; reading the question aloud would reach volunteers who find the written scale hard going.
- **More gold photos** — skill measurement is only as good as its reference set. Experts can already promote verified photos to gold from the review screen; the practice set needs to grow from 4 to dozens, with several per indicator.

---

## License

MIT
