# StreamSaathi

**An AI second opinion that makes every citizen stream observation more reliable, without replacing human judgment.**

`OneAquaHealth IEEE Global Hackathon` · `Track 3: AI-Supported Assessment` · Team **0xalgos**

> Live demo: _add Vercel URL_ · API docs: _add Render URL_/docs · Demo video: _add link_

## Problem

Citizen scientists often give wrong scores when assessing urban streams: terms are confusing, photos are blurry, GPS is off. So researchers can't trust the data.

## Solution

At every assessment step, the AI looks at the photo and gives a **suggested score, a reason and a confidence**. The citizen decides. (v2+) The system catches mistakes, computes a **Trust Score**, and routes low-trust observations to an **expert review queue**.

## v1 features

- Email/password + magic-link login (Supabase Auth)
- Guided, mobile-first assessment: one indicator per screen, big tap targets, progress bar
- Photo capture with client-side compression; server re-encodes and strips EXIF
- AI Second Opinion card: suggested label, confidence bar, reason, evidence chips, "Use AI's answer" / "Keep my answer"
- AI never blocks the flow: 20s timeout + fallback, user's own score is always saved
- History with pagination, detail page with private photos (signed URLs)

## Architecture

```
Browser (Next.js on Vercel)
   │  Supabase Auth (login) ──► JWT
   │  every API call: Authorization: Bearer <JWT>
   ▼
FastAPI (Render) ── verifies JWT (JWKS / HS256), checks ownership
   ├── Supabase Postgres (service key, RLS on as defence in depth)
   ├── Supabase Storage (private bucket, signed URLs)
   └── Vision LLM (Gemini / Groq) behind services/ai_opinion.py
```
AI key and Supabase service key never reach the browser.

## Responsible AI

1. **AI suggests, human decides.** The UI labels every AI output "AI suggestion · you decide". Both the human's original score and the AI score are stored.
2. **Honest uncertainty.** Confidence is always shown; the model is told to say `can_assess=false` instead of guessing.
3. **Fail safe.** If AI is down or returns garbage, the flow continues with the human's answer.
4. **Privacy.** Photos are private, EXIF (location/device) is stripped, access is via short-lived signed URLs.

## Tech stack

Next.js (App Router, TypeScript, Tailwind) · FastAPI + Pydantic v2 · Supabase (Postgres, Auth, Storage) · Gemini Flash / Groq vision · Vercel + Render · GitHub Actions

## Local setup

```bash
# 1. Supabase: run supabase/migrations/001_init.sql in the SQL editor
# 2. Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env   # fill values
uvicorn app.main:app --reload
# 3. Frontend
cd frontend && npm install && cp .env.example .env.local        # fill values
npm run dev
```
Tests: `cd backend && pytest -q` (no database needed).
Full deploy steps: [docs/DEPLOY.md](docs/DEPLOY.md). Feature roadmap and build notes: [docs/FEATURES_GUIDE.md](docs/FEATURES_GUIDE.md).

## API (v1)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Uptime check |
| GET | `/api/v1/indicators` | Config-driven indicator list |
| POST | `/api/v1/observations` | Create draft (lat, lng) |
| POST | `/api/v1/observations/{id}/indicators/{indicator_id}` | Multipart photo + human_score → AI opinion |
| PATCH | `/api/v1/observations/{id}/indicators/{indicator_id}` | Use AI's answer or keep own |
| POST | `/api/v1/observations/{id}/submit` | Validate required indicators, submit |
| GET | `/api/v1/observations/mine` | Paginated history |
| GET | `/api/v1/observations/{id}` | Detail with signed photo URLs |

Errors always look like `{"error": {"code": "AI_UNAVAILABLE", "message": "..."}}`.

## Indicators

Indicators live in `backend/app/config/indicators.json` (not hardcoded). Edit that file to match the OneAquaHealth protocol.

## Demo credentials

- Citizen: _add_
- Expert: _add (v3)_

## Roadmap

v2 Trust Score · v3 Expert review + tamper-evident audit log · v4 Micro-lessons, One Health card, map · v5 Calibration mode, disagreement heatmap, offline, multilingual.

## License

MIT
