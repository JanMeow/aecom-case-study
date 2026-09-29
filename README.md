# SGW Resilience Platform — Prototype

Prototype for the AECOM AI Solution Engineer case study. It shows the MVP workflow from the PRD end to end for Southeastern Grid & Water (SGW), a fictional power and water utility around Tampa Bay and Southwest Florida:

**six scattered data sources → one record per asset → risk score per asset as a hurricane approaches → rule-based alerts → an AI-assisted incident room with cited, human-approved briefings.** Two Phase 2 previews sit on top: a what-if storm forecast (ML) and tree canopy from satellite imagery (computer vision).

It replays **Hurricane Ian (2022)** using the real National Hurricane Center advisories. All SGW data (assets, staff, maintenance, field reports, playbooks) is mocked.

---

## Quick start

Two ways to run it: **Docker** (one command, nothing else to install) or **locally** (for development, with hot reload). Either way you need an Anthropic API key for the AI features; everything else works without it.

### Option A: Docker

Needs [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with Compose 2.24+).

```bash
cp backend/src/backend/.env.example backend/src/backend/.env   # then put your ANTHROPIC_API_KEY in it
docker compose up --build                                   # first build takes a few minutes
```

Open http://localhost:5173 (API docs at http://localhost:8000/docs), then follow [Sign in and replay](#sign-in-and-replay).

| Task | Command |
|---|---|
| Run in the background | `docker compose up --build -d` |
| Follow the logs | `docker compose logs -f` (or `logs -f backend`) |
| Stop | `docker compose down` (or Ctrl+C if running in the foreground) |
| After changing code | `docker compose up --build` (without `--build` you get the old image) |
| After changing `.env` | `docker compose up -d --force-recreate backend` (no rebuild needed) |

What runs:

| Container | Port | What it is |
|---|---|---|
| `backend` | 8000 | FastAPI on uvicorn (`backend/Dockerfile`, Python 3.13 + uv) |
| `frontend` | 5173 → 80 | nginx serving the built React app and forwarding `/api/*` to the backend (`frontend/Dockerfile`, `nginx.conf.template`) |

The API key is read from `.env` when the backend container starts; it is never built into an image. If ports 5173 or 8000 are busy (e.g. the local dev servers are still running), stop those first or change the left-hand port in `docker-compose.yml`.

### Option B: run locally

| Tool | Version | Used for |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | recent | Python backend (installs Python 3.13 and dependencies) |
| Node.js | 20.19+ (22 LTS recommended) | React frontend |

**1. Backend (FastAPI, port 8000)**

```bash
cd backend
cp src/backend/.env.example src/backend/.env     # then put your ANTHROPIC_API_KEY in src/backend/.env
uv sync                                         # creates .venv and installs dependencies
uv run backend                                  # starts http://127.0.0.1:8000
```

Interactive API docs: http://127.0.0.1:8000/docs

**2. Frontend (React + Vite, port 5173)**, in a second terminal:

```bash
cd frontend
npm install
npm run dev                                     # starts http://localhost:5173
```

Vite forwards `/api/*` to the backend on port 8000, so both must be running.

### Sign in and replay

1. Open http://localhost:5173 and pick a demo account (e.g. **Hannah Cole**, T&D Ops South supervisor). Any password works.
2. Press **▶ Play** on the timeline (left) or click any advisory.
3. Watch for the **first alerts** (27 Sep 2022 15:00 UTC) and the **incident room opening** (28 Sep 15:00 UTC).
4. In the incident room, type `/` for AI commands, e.g. `/generate_report`.

The processed data and trained ML model are committed, so nothing needs generating first (see [Regenerating data](#regenerating-data-and-the-model)).

---

## What the demo shows

The storyline is built into the data:

| Replay time (UTC) | What happens |
|---|---|
| 26 Sep | Ian is south of Cuba. Every asset is Low (green). |
| 27 Sep 15:00 (adv 18) | Forecast wind zones reach SW Florida. **First High alerts**: owners get inbox messages and notification banners. |
| 28 Sep 15:00 (adv 24) | `SUB-014` Fort Myers South turns **Critical** → the **incident room opens** with the owners of it and everything downstream, plus the Emergency Manager on duty. |
| 28 Sep 21:00 (adv 25) | Landfall: the peak, 5 Critical assets. Field reports show `SUB-014` out and `PS-007` on a portable generator. |
| 29 Sep | Ian moves inland; scores fall back to Low. |

In the incident room, `/generate_report` drafts a situation briefing that cites the exact playbook passages behind each action (e.g. PB-02 §7: *"PS-007… standby generator failed its June 2022 load test"*), and a person approves it.

---

## Architecture

```
 SOURCES (mock exports + real NHC data)             BACKEND (FastAPI)                                FRONTEND (React)
 ┌──────────────────────────────┐  batch job  ┌────────────────────────────────────────┐   REST   ┌────────────────────────┐
 │ GIS assets, dependencies,    │────────────▶│ ETL/extraction   → processed/assets.json│◀───────▶│ Login                  │
 │   critical facilities        │             │ ETL/risk_score   rules score (5 steps)  │          │ Map · timeline replay  │
 │ Maintenance register + WOs   │             │ ML/train_predict ML score (LightGBM)    │          │ Assets table · panel   │
 │ HR directory, on-call roster │             │ ETL/alerts       High → notify          │          │ Inbox · notifications  │
 │ Field app events (live) ─────┼── replay ──▶│                  Critical → open room   │          │ Incident room + dock   │
 │ Playbooks (markdown) ────────┼────────────▶│ LLM/service      Claude + citations     │─────────▶│   / commands, @ tags   │
 │ NHC Hurricane Ian advisories ┼────────────▶│ routers/         one router per area    │          └────────────────────────┘
 └──────────────────────────────┘             └────────────────────────────────────────┘
```

- **Batch baseline + live layer.** Slow-changing data (GIS, maintenance, HR) is joined once into `processed/assets.json`, as a nightly job would in production. Field events are layered on at replay time with `apply_field_events(assets, as_of)`.
- **Deterministic alerts, AI that advises.** Scores and alert rules are plain code: explainable and auditable. The AI only drafts and answers, and a person approves.
- **Rules score drives alerts; ML is shown alongside** as a Phase 2 preview.

---

## Data

All in `backend/src/backend/data/` (details in [its README](backend/src/backend/data/README.md)).

| Source system | File | Format |
|---|---|---|
| GIS | `sources/gis/assets.geojson`, `dependencies.csv`, `critical_facilities.geojson` | GeoJSON / CSV |
| Maintenance (CMMS) | `sources/maintenance/asset_register.csv`, `work_orders.csv` | CSV |
| Staff (HR) | `sources/staff/hr_directory.csv`, `on_call_roster.csv` | CSV |
| Field operations | `sources/field_ops/events.jsonl` | JSON lines (webhooks) |
| Emergency plans | `sources/plans/PB-01 … PB-05.md` | Markdown |
| Weather (real) | `sources/weather/ian_2022/advisories.geojson` (17 advisories, 26–29 Sep 2022) | GeoJSON, converted from NHC shapefiles |
| ML training (synthetic) | `ml/storm_outcomes.csv` (400 simulated storms × 58 assets) | CSV |

Scale: 58 assets (substations, lines, power plants, water and wastewater plants, pumping stations), 75 dependency links, 16 critical facilities, 19 staff.

---

## Risk scoring

**risk = likelihood × consequence**, in five steps (`ETL/risk_score.py`; every setting in `ETL/threshold.py`):

| Step | Function | Rule |
|---|---|---|
| 1. Wind zone | `wind_zones()` | Which 34 / 50 / 64 kt zone the asset is in now, and which is forecast within 36 h |
| 2. Own chance | `own_chance()` | Lookup table (asset type × zone) × condition (4/5 → ×1.3) + 30% if in a FEMA flood zone (AE/VE) and the 64 kt zone; a forecast counts 75% |
| 3. Likelihood | `likelihood()` | max(own chance, likelihood of what it depends on); a backup generator halves inherited power risk |
| 4. Consequence | `consequence()` | Customers affected (own + downstream) ÷ 500k + 0.1 per critical facility, capped at 1 |
| 5. Score and tier | `final_score()` | likelihood × (0.5 + 0.5 × consequence) → Critical ≥ 0.75, High ≥ 0.50, Medium ≥ 0.25 |

Example, `SUB-014` at advisory 24: substation in the 64 kt zone → 50%; ×1.3 condition, +30% flood → 95%; 246,000 customers and 5 critical facilities → consequence 0.99; score **0.95 Critical**.

**ML score** (`ML/train_predict.py`): replaces only step 2 with a LightGBM model trained on synthetic storm outcomes. It also uses tree cover, age, elevation, line length and past storm failures. On 80 unseen storms it beats the rules (Brier 0.117 vs 0.134, AUC 0.870 vs 0.858), and explains each prediction with SHAP values. Labels are synthetic, so this shows the pipeline, not real accuracy.

**What-if forecast** (`GET /forecast`, Forecast panel on an asset): "what if a 34 / 50 / 64 kt storm hit this asset, its region or the whole area?". `ml_simulate_risk_score()` replaces step 1 with the chosen wind zone for the assets hit (0 elsewhere), then runs the same ML steps 2–5, so the cascade is included: with `scope=region` an asset's suppliers are hit too.

---

## Alerts (deterministic)

`ETL/alerts.py` replays every advisory up to the current one, so moving the timeline backwards gives the same result.

- **High** → message to the asset's owner.
- **Critical** → open the incident room (or add to it). Members: owners of each Critical asset and everything downstream of it, plus the Emergency Manager on duty (from the on-call roster).
- Each asset alerts once per tier, and again only if its tier rises.

---

## AI in the incident room

Plain messages go to the people in the room. Only slash commands call Claude (default `claude-opus-5-5`; switch with `/model`):

| Command | Endpoint | Does |
|---|---|---|
| `/ask question` | `POST /llm/ask` | Question about the current situation (storm, assets at risk, any asset named). Answers from the data; no playbook citations |
| `/generate_report [asset]` | `POST /llm/report` | Situation briefing in PB-04 §4's five sections; defaults to the room's trigger asset. Draft + **Approve** |
| `/playbook [asset] question` | `POST /llm/playbook` | What the playbooks say for that asset |
| `/model [id]` | `GET /llm/models` | Switch the Claude model (Opus 5.5, Sonnet 5, Haiku 4.5, Fable 5.1); every AI answer shows which model wrote it |

- **Verifiable citations.** Playbooks are sent as documents with Anthropic's **Citations** feature (`LLM/playbook.py`). The API returns the exact passage behind each claim; hovering a `PB-02 §7` chip shows it. With only 5 short playbooks, no retrieval is needed; at scale, a retrieval step (e.g. pgvector) would pick the sections, with the same citation format.
- **Prompt caching** on the playbook documents; reports cached per (advisory, asset).
- **Guardrails in the prompts:** take every number from the data, say what's missing, recommend but never decide.

---

## Computer vision: tree canopy (Phase 2 preview)

The **Tree canopy** panel on an asset (`POST /cv/tree_canopy_pct`, `CV/`) checks the GIS vegetation record against imagery:

1. `esri.py`: satellite image of the area around the asset from Esri World Imagery (300 m; 800 m for lines).
2. `green_pixel.py`: **green cover** by pixel colour, no model: Excess Green index (2g − r − b) with a per-image Otsu threshold, clamped to 0.03–0.15. Returns the % and a highlighted mask. Counts grass as well as trees.
3. `inference.py`: Claude vision (structured output, `CanopyInference`) estimates **tree canopy only**, with notes on trees near equipment. The GIS value is left out of the prompt, so it is an independent check.

The panel shows GIS vs measured green vs AI canopy side by side. Results are not fed back into the ML score yet.

---

## API

| Method | Path | Returns |
|---|---|---|
| GET | `/assets`, `/assets/{id}` | Asset list for the map; one full aggregated record |
| GET | `/advisories`, `/advisories/{n}/map` | Replay timeline; one advisory as GeoJSON (cone, track, wind zones) |
| GET | `/risks?advisory=n` | Rules and ML scores per asset, with reasons and field status |
| GET | `/alerts?advisory=n` | Alerts sent so far and the incident room |
| GET | `/people` | Staff directory |
| GET | `/forecast?asset_id=&wind_zone=34\|50\|64&scope=asset\|region\|all` | What-if ML risk for one asset, and how many assets are hit |
| GET | `/llm/models` | Claude models available to `/model` |
| POST | `/llm/ask`, `/llm/report`, `/llm/playbook` | AI answers with citations |
| POST | `/cv/tree_canopy_pct` | Satellite image, green cover and Claude's canopy estimate for an asset |

---

## Repository structure

```
backend/
  pyproject.toml, uv.lock
  src/backend/
    main.py                 FastAPI app: CORS + routers
    routers/                assets, advisories, risk, people, llm, cv (+ shared.py: data loaded once, checks)
    api/model.py            API response and request shapes
    ETL/                    extraction.py (aggregate), risk_score.py, threshold.py, alerts.py, model.py
    ML/train_predict.py     train / predict the ML score
    LLM/                    service.py (Claude calls, MODELS), prompt.py, playbook.py (citations), model.py
    CV/                     esri.py (imagery), green_pixel.py (green cover), inference.py (Claude vision)
    config/setting.py       loads .env (ANTHROPIC_API_KEY)
    data/                   sources, processed baseline, ML data and model (see data/README.md)
    scripts/                generate.py (mock data), convert_nhc.py (NHC shapefiles → GeoJSON)
frontend/
  src/
    main.tsx                routes: /login and the app
    store.ts                app state (Zustand)
    api.ts, types.ts        backend calls and types
    commands.ts             incident room slash commands
    colors.ts, index.css    colour palette (defined once in index.css)
    components/             MapView, Timeline, AssetPanel, DependencyGraph, AssetTable, Inbox,
                            IncidentRoom, RoomDock, ChatInput, AiMessage, Notifications, CanopyPanel,
                            ForecastPanel, Login, ...
```

---

## Regenerating data and the model

Everything below is already committed; run only to change the data.

```bash
cd backend
uv run python src/backend/scripts/generate.py                              # mock source systems + ML training data
uv run --with pyshp python src/backend/scripts/convert_nhc.py              # NHC shapefiles → advisories.geojson
uv run python -c "from backend.ETL.extraction import save; save()"         # rebuild processed/assets.json
uv run python -m backend.ML.train_predict                                  # retrain the ML model, print metrics
```

---

## Built vs not implemented

| Feature | Status |
|---|---|
| Aggregation of 6 sources, rules score, alerts, replay | Built |
| ML score with explanations (Phase 2 preview) | Built |
| Map, dependency lines and diagram, asset table, inbox, notifications | Built |
| Incident room: AI commands, citations, report approval, @ tags, invites | Built |
| Fake login with demo accounts | Built |
| What-if storm forecast (ML), tree canopy from satellite imagery, `/model` switching | Built (Phase 2 previews) |
| AI posts first when the room opens (PRD F10) | Partly: the briefing is drafted when someone types `/generate_report` |
| Threshold editing (F8), event log (F12), resource pre-allocation (F13), AI quick actions (F14) | Not implemented |
| Storm surge, Teams / SMS delivery | Not implemented: surge is approximated by the flood-zone bonus; alerts appear in the app |
| Full tool-use (ReAct) loop for the AI | Not implemented: the AI gets the relevant data in one call |
| Event bus and live NWS weather feed | Not implemented: the replay plays the role of incoming advisories |
| Playbook retrieval (embeddings) | Not implemented: not needed for 5 playbooks |
| Docker Compose (backend + nginx frontend) | Built |
| Asset similarity search, 3D map | Not implemented |

## Assumptions and limitations

- All SGW data is mocked; Hurricane Ian advisories are real NHC data.
- Scoring settings are illustrative, in the style of FEMA Hazus damage tables, not calibrated engineering values. Calibration against SGW's outage history is what the ML mode is for.
- ML labels are synthetic.
- Assets are fictional but placed at real coordinates, so some satellite images show unrelated sites (e.g. `SUB-014` sits on an airport). The canopy estimate comes from a general vision model, not a trained segmentation model, and the image date is unknown.
- Chat, invites and report approvals are kept in the browser only; nothing is stored or sent. In production the incident room would be a Microsoft Teams channel, and approvals would be stored as an audit trail.
- The login is fake (no authentication). Production would use SGW single sign-on.
- The AI uses the public Anthropic API; production would use a private endpoint (e.g. AWS Bedrock or Azure).

## Production equivalents

| Demo | Production |
|---|---|
| Batch job to `assets.json` | Scheduled pipeline into Postgres + PostGIS |
| Replay of saved advisories | Event bus (e.g. Azure Event Grid) + a function polling NWS |
| In-memory caches | Database tables (reports, approvals, audit log) |
| Built-in incident room | Microsoft Teams channel + bot via Microsoft Graph |
| All playbooks in the prompt | Retrieval with embeddings (pgvector), same citation format |

## How AI was used to build this

I designed the architecture, data model, scoring logic and demo storyline, and used Claude Code to implement and iterate quickly. I simplified whenever it grew more complex than the story needed (e.g. replacing damage curves with a lookup table) and verified behaviour against the data and the live API at each step.
