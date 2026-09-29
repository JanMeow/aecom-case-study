# Mock data

SGW's source systems, mocked as the exports each real system would produce. Company data is fictional. Hurricane Ian weather data is real (NHC archive).

```bash
# from backend/src/backend/
python scripts/generate.py                                     # regenerate mock sources (stdlib only, seeded)
uv run --no-project --with pyshp python scripts/convert_nhc.py # re-convert NHC shapefiles (outputs are committed)
```

## Files

| Source system | File | Format | Notes |
|---|---|---|---|
| GIS | `sources/gis/assets.geojson` | GeoJSON | 58 assets. **System of record for IDs** (`SUB-014`). Lines are LineStrings, the rest Points |
| GIS | `sources/gis/dependencies.csv` | CSV | 75 links, each "downstream depends on upstream": `power`, `water`, `wastewater` (a lift station depends on its treatment plant) |
| GIS | `sources/gis/critical_facilities.geojson` | GeoJSON | 16 hospitals, shelters, EOCs, nursing homes, with the substation and pumping station that serve each |
| Maintenance (CMMS) | `sources/maintenance/asset_register.csv` | CSV | Equipment master: condition rating, install date, criticality, `OWNER_EMPLOYEE_ID` |
| Maintenance (CMMS) | `sources/maintenance/work_orders.csv` | CSV | 203 work orders 2017–2022, including damage from Irma 2017, Eta 2020 and Elsa 2021 |
| Field operations | `sources/field_ops/events.jsonl` | JSON lines (webhooks) | 29 events during Ian, each with `received_at`. Replay emits them when the clock passes that time |
| Staff (HR) | `sources/staff/hr_directory.csv` | CSV | 19 staff: names, titles, teams, contacts. Joined through the CMMS owner ID |
| Staff | `sources/staff/on_call_roster.csv` | CSV | Emergency Manager on duty (hand-over at 2022-09-28 12:00Z) |
| Emergency plans | `sources/plans/PB-0*.md` | Markdown | 5 playbooks with numbered sections, cited as `[PB-02 §4]` |
| Weather | `sources/weather/ian_2022/raw/*.zip` | NHC shapefiles | Real advisories 12–28 (26–29 Sep 2022) |
| Weather | `sources/weather/ian_2022/advisories.geojson` | GeoJSON | All 17 advisories in one file. `properties.advisories` lists them in replay order (issue time, centre, max wind, category). Each feature has an `advisory` number and a `layer`: `cone`, `track`, `forecast_point`, `wind_radii` (34/50/64 kt, current and forecast) or `watch_warning` |
| ML (synthetic) | `ml/storm_outcomes.csv` | CSV | 400 simulated storms × 58 assets = 23,200 rows, `failed` label (~16% positive) |

## How the sources join

```
GIS asset_id (base record)
     ├── dependencies.csv ──► upstream / downstream (cascade graph)
     ├── critical_facilities.geojson (power_from / water_from) ──► impact
     ├── CMMS EQUIP_NO ──► condition, history
     │        └── OWNER_EMPLOYEE_ID ── HR EMPLOYEE_ID ──► owner name, title, contact
     └── field events (asset_id, up to the replay clock) ──► live status
```

The baseline (everything except field events) is built once by `ETL/extraction.py` `save()` into `data/processed/assets.json`. Field events are layered on at replay time with `apply_field_events()`.

## Keeping it simple

Every system uses the same asset ID (the GIS `asset_id`) and ISO dates, so the aggregator only joins; it doesn't clean. The sources still differ where it matters for the demo: file format (GeoJSON, CSV, JSON lines, markdown, shapefiles), column names, update rhythm (daily GIS, nightly CMMS, real-time field events).

## The story in the data

- **Advisories 12–19 (26–27 Sep):** Tampa Bay is inside the 5-day cone (37–49 assets) but no wind zones yet. Forecast points pass near Tampa at 48–60 h. Risk should rise from the **forecast** radii, not the current ones.
- **Advisories 20–23 (28 Sep, early):** the track shifts south. Tropical-storm winds reach 11–49 assets.
- **Advisory 24 (28 Sep 15:00Z):** 64 kt winds over Fort Myers and Cape Coral: `SUB-014`, `SUB-015`, `SUB-017`, `WTP-002`, `WTP-005`, `WWTP-003`, `PS-007`, `PS-014`.
- **Advisory 25:** landfall. 64 kt winds over 24 assets from Sarasota to Lee County.
- **Advisory 26 onward:** the storm moves inland and away. Scores fall.

The weak points are planted in maintenance and playbooks, so the AI has something real to find:
- **`SUB-014` Fort Myers South** (condition 4): single supply via `TL-008`, transformer under temporary repair. It feeds `PS-007`, `WTP-002`, `WWTP-003`, `PS-017` and Caloosa Regional Medical Center.
- **`TL-008`:** deferred crossarm repair and trees near the line (spans 14–19). The field events show those spans failing.
- **`PS-007`:** standby generator removed in June 2022. It serves a hospital and a shelter.
- **`SUB-017` / `PS-016` Fort Myers Beach:** 1 m elevation, both flooded in Irma 2017.

Field events confirm the outcome: `TL-008` locks out, which takes out `SUB-014`, and `PS-007` runs on a portable generator.

## How the risk score uses the data

See `ETL/risk_score.py` (logic) and `ETL/threshold.py` (settings).

- **Wind zone:** the strongest 34/50/64 kt polygon containing the asset's location, now or forecast within 36 h (lines use their midpoint).
- **Base chance:** a lookup table by `asset_type` and wind zone.
- **Condition:** `condition_rating` from CMMS multiplies the chance.
- **Flood:** a `flood_zone` of AE or VE adds 30% inside the 64 kt zone.
- **Cascade:** `upstream` links pass their likelihood down. `has_backup_power` halves what a failed power supply passes on.
- **Consequence:** `customers_served` and `critical_facilities`, for the asset and everything `downstream`.
- **`tree_canopy_pct`:** in the GIS data, but **the rules formula ignores it**. It is the hidden factor the ML model can learn. Currently set by `generate.py`; the Tree canopy panel (CV) checks it against satellite imagery.

## Synthetic ML labels

`ml/storm_outcomes.csv`: 400 simulated storms × 58 assets = 23,200 rows, about 16% labelled `failed`. Generated by `write_ml()` in `scripts/generate.py`.

**Features** are only things the live system can supply: the wind zone (from the advisory, as in the rules) and `AggregatedData` fields.

| Feature | Rules use it? | Source |
|---|---|---|
| `wind_zone_kt` (0/34/50/64), `asset_type`, `condition_rating`, `flood_zone` | Yes | Advisory, GIS, CMMS |
| `tree_canopy_pct` | No (ML only) | GIS |
| `age_years` | No (ML only) | GIS `install_year` |
| `elevation_m` | No (ML only) | GIS |
| `length_km` (0 unless a line) | No (ML only) | GIS `attributes` |
| `past_storm_failures` | No (ML only) | CMMS `history` (STORM work orders) |

The forecast discount is not a feature. A model predicts as if the zone arrives, and the 75% forecast weight is applied afterwards, as in the rules.

**Labels** come from `true_chance()`. It starts from the same lookup table as the rules, then adds effects the rules ignore:
- tree cover (lines and substations)
- equipment over 30 years old
- line length
- past storm failures
- surge that depends on elevation, instead of a flat bonus

The labels are then sampled with randomness.

**Result** from `python -m backend.ML.train_predict` (LightGBM, trained on 320 storms, tested on 80 unseen storms, only assets inside a wind zone):

| Model | AUC | Brier score (lower is better) |
|---|---|---|
| Rules | 0.858 | 0.134 |
| ML | 0.870 | 0.117 |

The model's top extra features are past storm failures, line length and age. Labels are capped at 95%, since no failure is certain. The trained model is saved to `ml/model.txt`.

The labels are synthetic, so this demonstrates the pipeline and explanations, not real-world accuracy.
