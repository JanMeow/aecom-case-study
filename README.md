# SGW Resilience Platform — Prototype

Prototype for the AECOM AI Solution Engineer case study. It shows the MVP workflow from the PRD end to end for Southeastern Grid & Water (SGW), a fictional utility: scattered data sources are combined into one asset picture, assets are scored against a hurricane, rules raise alerts, and an AI assistant briefs the incident room.

All company data is mocked. The hurricane data is real public data (Hurricane Ian, 2022).

> **Status: in development.** Items tagged `nice-to-have` are planned but may not be implemented at submission. Anything not built will be marked "not implemented" here before submitting.

---

## 1. What the demo shows

```
Six scattered sources ─► Aggregator ─► One asset table
                                              │
Hurricane Ian advisory (replay) ─► event: weather.advisory_issued
                                              │
                               Storm mode: re-score every 15 min (20 s in the demo)
                                              │
                          Risk score per asset (rules, or ML `nice-to-have`)
                                              │
                    High ─► notify asset owners      Critical ─► open incident room
                                                                   │
                                          AI posts briefing + draft report (cited)
                                          People ask questions, AI answers with tools
                                          Emergency manager approves the report
```

Why Hurricane Ian: early forecasts pointed at Tampa Bay, then the track shifted south to Fort Myers. Replaying the advisories shows risk scores rising and then falling as the forecast changes, which is the situation the platform is built for.

---

## 2. Architecture

```
┌─────────────────────── FRONTEND (React) ───────────────────────┐
│  Risk map │ Asset panel │ Alert feed │ Incident room │ Event log │
└──────▲──────────────────────────────────────────────┬─────────┘
       │ SSE: GET /stream (all live events)           │ REST
┌──────┴──────────────────────────────────────────────▼─────────┐
│                        BACKEND (FastAPI)                        │
│                                                                 │
│  Connectors ─► Aggregator ─► Asset store (SQLite)               │
│                                                                 │
│  Weather connector (replay | live `nice-to-have`)               │
│        │                                                        │
│        ▼                 in-process event bus                   │
│  weather.advisory_issued ─► Scheduler ─► Risk engine            │
│                                  risk.scored ─► Rules engine    │
│                     alert.raised / room.opened ─► AI service    │
│                                  ai.step / ai.token ─► SSE      │
└─────────────────────────────────────────────────────────────────┘
```

Everything runs in one FastAPI process. The event bus, AI service and scheduler are separate modules with clear interfaces, so each can move to its own service in production (see section 11).

---

## 3. Mock data sources

Each source is generated in the format SGW's real system would export. To keep the demo focused, all systems share the GIS asset ID and use ISO dates, so the aggregator joins rather than cleans. See `backend/src/backend/data/README.md`.

| Source | Format | What it adds |
|---|---|---|
| GIS asset map | GeoJSON | Assets, locations, elevation, dependencies, critical facilities (system of record for IDs) |
| Maintenance | CSV export | Condition rating, work order and storm damage history |
| Weather | Real NHC advisories for Hurricane Ian (cone, track, wind radii) | The hazard; real data |
| Field operations | JSON webhook events | Live status; events arrive over time during the replay |
| Emergency plans | 4–5 markdown playbooks | Unstructured text, searched by the AI |
| Staff directory | HR CSV | Owner names and contacts; joined through the owner ID in the maintenance register |

Scale: 58 assets from Tampa Bay to Fort Myers (substations, transmission lines, power plants, water and wastewater plants, pumping stations), 75 dependency links, 16 critical facilities, 19 staff.

## 4. Aggregator

1. **Load GIS** as the base record for every asset.
2. **Join** each other source onto it by asset ID: dependencies and facilities (GIS), condition and history (maintenance), owner (HR via team responsibilities), live status (field events up to the replay clock).

Code: `backend/src/backend/ETL/extraction.py` (`aggregate()`), models in `ETL/model.py`.

The output is one combined asset table that every other part of the system reads.

---

## 5. Event-driven design

An in-process publish/subscribe bus (asyncio) using production-style topic names:

| Topic | Published by | Consumed by |
|---|---|---|
| `weather.advisory_issued` | Weather connector | Scheduler (starts storm mode) |
| `field.event_received` | Field ops connector | Asset store |
| `risk.scored` | Risk engine | Rules engine, SSE |
| `alert.raised` | Rules engine | Alert feed, SSE |
| `room.opened` | Rules engine | AI service (first briefing) |
| `ai.step` / `ai.token` / `ai.done` | AI service | SSE (everyone in the room) |
| `report.approved` | API | Event log |
| `storm.cleared` | Weather connector | Scheduler (stops storm mode) |

**Storm lifecycle:** idle → active (re-scoring every 15 minutes; 20 seconds in the demo) → cleared. Only the weather connector starts and stops it, so replay and live mode behave the same.

- **Event log panel** `nice-to-have`: streams every event in the UI, to make the design visible.
- **Live weather mode** `nice-to-have`: polls the NWS `/alerts/active` API instead of replaying files.

---

## 6. Risk scoring

### Rules mode (MVP, default)

**risk = likelihood × consequence**

```
1. wind zone     which wind zone (34 / 50 / 64 kt) is the asset in now, and which is forecast (≤ 36 h)?
2. own chance    lookup table (asset type × wind zone) × condition (4/5 → ×1.3) + 30% if in a FEMA flood zone
                 and the 64 kt zone; a forecast zone counts 75%
3. likelihood    max(own chance, likelihood of what it depends on); a backup generator halves power risk
4. consequence   customers affected (own + downstream) ÷ 500k + 0.1 per critical facility, capped at 1
5. score         likelihood × (0.5 + 0.5 × consequence)  → tier
```

Example, `SUB-014` at landfall: substation in the 64 kt zone → 50%; condition 4/5 ×1.3 and flood zone AE +30% → 95%; it affects 246,000 customers and 5 critical facilities → consequence 0.99; score 0.95 → **Critical**.

Settings live in `ETL/threshold.py`. Every step is stored in the result, so the UI and the AI can explain it.

### ML mode `nice-to-have` (Phase 2 preview)

- **Model:** LightGBM classifier, selected with a toggle in the UI.
- **Labels:** synthetic past-storm outcomes, generated as the rules formula plus noise plus one hidden factor the formula ignores (vegetation density). The model can then learn something the rules miss, and the UI shows where the two modes disagree.
- **Explanations:** per-asset SHAP values from LightGBM's `pred_contrib=True`, shown as "why is this asset high?" bars.
- **Caveat:** the labels are synthetic, so this demonstrates the pipeline, not accuracy.

### Asset similarity `nice-to-have`

- Each asset becomes a feature vector (standardised numeric features plus one-hot asset type).
- Cosine similarity via scikit-learn `NearestNeighbors` finds "assets like this one", including ones that failed in past storms.
- Exposed to the AI as the `find_similar_assets` tool. Production would use pgvector.

---

## 7. Alert rules (deterministic, no AI)

| Tier | Score | Action |
|---|---|---|
| Low / Medium | < 0.50 | Update the map only |
| **High** | ≥ 0.50 | Notify the asset's owner |
| **Critical** | ≥ 0.75 | Open an incident room (or add to the open room for this storm) |

- Each asset alerts once per tier, and again only if its tier rises.
- Room members: the owner of the critical asset, owners of its downstream assets, and the emergency manager on duty.
- Thresholds live in `thresholds.yaml`, so they change without code changes.

---

## 8. AI service

Two jobs, two patterns:

| Job | Trigger | Pattern |
|---|---|---|
| First briefing + draft report | `room.opened` | **Fixed pipeline.** Code gathers the critical assets, dependents, score breakdowns and top playbook sections, then makes one LLM call that writes the briefing in a set structure. Reliable, because it runs automatically. |
| Questions in the room | A user message | **Tool-use loop (ReAct)**, capped at 5 turns. Simple questions finish in one turn. If the cap is reached, a final call without tools forces an answer that says what is missing. |

- **Model:** Claude (`claude-sonnet-5`) through the Messages API with native tool use. The loop is plain Python, with no agent framework: routing is simple, and every step is easy to audit.
- **Tools (all read-only):**

  | Tool | Returns |
  |---|---|
  | `get_asset(id)` | Combined asset record and score breakdown |
  | `get_dependents(id)` | Downstream assets, customers and critical facilities affected |
  | `get_asset_history(id)` | Past incidents |
  | `get_active_hazard()` | Current advisory, cone and wind zones |
  | `search_playbooks(query)` | Relevant playbook sections, with section IDs for citation |
  | `save_draft_report(...)` | Saves a structured draft report (status `draft`) |
  | `find_similar_assets(id)` `nice-to-have` | Most similar assets and their storm history |

- **Playbook search (RAG):** playbooks are split at their headings, embedded locally with `fastembed` (bge-small), and searched by similarity. Every claim cites its source, e.g. `[PB-02 §3]`. BM25 keyword search is the fallback.
- **System prompt rules:** take every number from a tool, cite a source for every fact, say when unsure, recommend but never act.
- **Approval:** the Approve button is plain code that sets the report to `approved` and logs who approved it. The AI cannot approve.
- **Shared replies:** `POST /rooms/{id}/messages` returns immediately. The reply streams to everyone in the room as `ai.step` ("Checking dependents of SUB-014…") and `ai.token` events over the single SSE stream.

---

## 9. Frontend

| Concern | Choice |
|---|---|
| Framework | React + Vite + TypeScript |
| Styling | Tailwind + shadcn/ui |
| Client state | Zustand (selected asset, scoring mode, open room, live events) |
| Server state | TanStack Query; SSE events update the store or refresh queries |
| Map | MapLibre GL (react-map-gl) with free tiles |
| Dependency graph `nice-to-have` | React Flow or Cytoscape.js |

**Screens:**
- **Risk map:** assets coloured by tier, the forecast cone and track, and replay controls (next advisory / auto-play).
- **Asset panel:** combined data from every source, with the score breakdown (and SHAP bars in ML mode `nice-to-have`).
- **Alert feed:** who was notified, when, and which rule fired.
- **Incident room:** chat with an AI badge and live tool steps, the draft report card, and the Approve button.
- **Dependency graph** `nice-to-have`: the selected asset's network, with failures cascading visibly.
- **Event log** `nice-to-have`: every bus event as it fires.

---

## 10. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/assets` | Assets with latest scores (GeoJSON) |
| GET | `/assets/{id}` | Combined record, score breakdown, history |
| GET | `/graph?root={id}` | Dependency subgraph |
| POST | `/replay/next` | Next advisory (demo control) |
| POST | `/replay/auto` | Start or stop auto-play |
| PUT | `/scoring/mode` | `rules` or `ml` `nice-to-have` |
| GET | `/stream` | SSE: scores, alerts, rooms, AI steps and tokens |
| GET | `/rooms/{id}` | Room, members, messages, draft report |
| POST | `/rooms/{id}/messages` | Post a message; the AI reply arrives on `/stream` |
| POST | `/reports/{id}/approve` | Approve the draft report |

## Data model (SQLite)

| Table | Key fields |
|---|---|
| `assets` | id, name, type, lat, lon, elevation, age, condition, customers, critical_facilities, owner_id |
| `dependencies` | upstream_id, downstream_id, has_backup |
| `people` | id, name, role, team, contact |
| `hazard_updates` | id, source, advisory_no, cone_geojson, wind_geojson, issued_at |
| `risk_scores` | asset_id, hazard_update_id, mode, score, tier, breakdown_json |
| `notifications` | id, asset_id, person_id, tier, rule, created_at |
| `rooms` / `room_members` | room id, storm, status; members |
| `messages` | id, room_id, author, content, citations_json, created_at |
| `reports` | id, room_id, content_json, status, approved_by, approved_at |
| `events` | id, topic, payload_json, created_at |

---

## 11. Production equivalents

| Demo | Production |
|---|---|
| In-process event bus | Azure Event Grid or Service Bus (or AWS EventBridge), same topic names |
| Replay connector / scheduler | Function polling the weather API, publishing `weather.advisory_issued` |
| SQLite | Postgres + PostGIS + pgvector |
| Built-in incident room | Microsoft Teams channel and bot via Microsoft Graph |
| Public Claude API | Private endpoint (Azure or AWS Bedrock) |
| AI module in the API process | Separate AI service |
| Plain tool-use loop | LangGraph or similar, once action workflows need pauses and multi-person sign-off (Phase 3) |
| No auth | Company single sign-on and role-based access |

---

## 12. Repository structure

```
aecom-case-study/
├── backend/
│   ├── pyproject.toml
│   └── src/backend/
│       ├── main.py            # FastAPI app, routes, SSE
│       ├── bus.py             # in-process event bus
│       ├── connectors/        # gis, maintenance, field_ops, staff, weather (replay / live)
│       ├── ETL/               # extraction.py (aggregate), risk_score.py, model.py
│       ├── risk/              # rules.py, cascade.py, ml.py, similarity.py
│       ├── alerts/            # thresholds.yaml, rules engine
│       ├── ai/                # briefing pipeline, agent loop, tools, playbook search
│       ├── db.py              # SQLite models
│       ├── data/              # mock sources + real Hurricane Ian advisories (see data/README.md)
│       │   ├── sources/       # one folder per source system
│       │   └── ml/            # synthetic training data (ML mode)
│       └── scripts/           # generate.py (mock data), convert_nhc.py (NHC shapefiles → GeoJSON)
├── frontend/                  # React app
└── docker-compose.yml         # `nice-to-have`
```

## 13. Running locally

Requires Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 20+, and an Anthropic API key.

```bash
# backend
cd backend
export ANTHROPIC_API_KEY=...
python src/backend/scripts/generate.py   # optional: data is committed; this regenerates it
uv run fastapi dev src/backend/main.py

# frontend (second terminal)
cd frontend
npm install && npm run dev
```

**Docker Compose** `nice-to-have`: `docker compose up` runs the API and the web app together.

---

## 14. Assumptions and limitations

- All asset, people, maintenance and field data is mocked. Hurricane Ian advisories are real NHC data.
- The rules score is a simplified, explainable formula, not a calibrated engineering model.
- ML mode `nice-to-have` is trained on synthetic labels. It shows the pipeline, not real accuracy.
- The incident room is built into the app. In production it would be a Teams channel.
- No authentication. The AI is read-only and cannot take operational actions.
- Storm mode runs on a compressed clock (20 seconds instead of 15 minutes).

## 15. Future work

- Teams bot and Microsoft Graph integration
- ML scoring trained on SGW's real outage history, with SHAP explanations (Phase 2)
- Action tools with 2–3 person sign-off (Phase 3)
- Repair-cost estimation and crew optimisation (Phase 3)
- More hazards: flood, wildfire, heat
