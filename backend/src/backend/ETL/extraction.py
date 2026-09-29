"""
extracting all sources of data from /data into required format

For example
{
    "asset_id": "SUB-014", "name": "Fort Myers South", "type": "substation", "region": "South",
    "location": {"lat": 26.58, "lon": -81.87}, "elevation_m": 3.0, "flood_zone": "AE",
    "condition_rating": 4, "install_year": 1974, "customers_served": 44000,
    "has_backup_power": false, "backup_hours": 0,
    "owner": {"employee_id": "E1007", "name": "Hannah Cole", "team": "T&D Ops South"},
    "upstream": [{"asset_id": "TL-008", "type": "power"}],
    "downstream": ["WTP-002", "WWTP-003", "PS-007", "PS-017"],
    "critical_facilities": ["CF-008", "CF-012"],
    "history": [{"date": "2022-03-14", "type": "CM", "summary": "Transformer T2 bushing oil leak"}],
    "sources": ["gis", "cmms", "hr", "field_ops"]
  }

Batch baseline (save() -> data/processed/assets.json):
    GIS assets -> + dependencies -> + critical facilities -> + CMMS condition, history, owner (HR)
Live layer (apply_field_events): field app events up to the replay clock set each asset's status.
"""
import csv
import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from backend.ETL.model import (Advisory, AggregatedData, CriticalFacility, FieldEvent, HistoryItem, Link, Location,
                               Owner, WindZone)

DATA = Path(__file__).parents[1] / "data"
SOURCES = DATA / "sources"
WEATHER = SOURCES / "weather" / "ian_2022"
PROCESSED = DATA / "processed" / "assets.json"


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# One step per source system
# ---------------------------------------------------------------------------
_GIS_CORE = {"asset_id", "name", "asset_type", "region", "elevation_m", "flood_zone",
             "install_year", "customers_served", "has_backup_power", "backup_hours", "tree_canopy_pct"}


def _load_gis() -> dict[str, AggregatedData]:
    """GIS is the system of record: one base record per asset."""
    assets = {}
    for f in json.loads((SOURCES / "gis" / "assets.geojson").read_text())["features"]:
        p, geom = f["properties"], f["geometry"]
        if geom["type"] == "LineString":
            path = [tuple(c) for c in geom["coordinates"]]
            lon, lat = path[len(path) // 2]
        else:
            path, (lon, lat) = None, geom["coordinates"]
        assets[p["asset_id"]] = AggregatedData(
            asset_id=p["asset_id"], name=p["name"], type=p["asset_type"], region=p["region"],
            location=Location(lat=lat, lon=lon), path=path,
            elevation_m=p["elevation_m"], flood_zone=p["flood_zone"],
            install_year=p["install_year"], customers_served=p["customers_served"],
            has_backup_power=p["has_backup_power"], backup_hours=p["backup_hours"],
            tree_canopy_pct=p["tree_canopy_pct"],
            attributes={k: v for k, v in p.items() if k not in _GIS_CORE},
            sources=["gis"],
        )
    return assets


def _add_dependencies(assets: dict[str, AggregatedData]) -> None:
    """Each row: downstream depends on upstream. Stored on both ends so the graph can be walked either way."""
    for r in _read_csv(SOURCES / "gis" / "dependencies.csv"):
        up, down = r["upstream_id"], r["downstream_id"]
        assets[down].upstream.append(Link(asset_id=up, type=r["dependency_type"]))
        assets[up].downstream.append(down)


def _add_facilities(assets: dict[str, AggregatedData]) -> None:
    """Each facility is attached to the asset that powers it and the one that supplies its water."""
    for f in json.loads((SOURCES / "gis" / "critical_facilities.geojson").read_text())["features"]:
        p = f["properties"]
        for key, via in (("power_from", "power"), ("water_from", "water")):
            assets[p[key]].critical_facilities.append(
                CriticalFacility(facility_id=p["facility_id"], name=p["name"], kind=p["kind"], via=via))


def _add_maintenance(assets: dict[str, AggregatedData]) -> None:
    """CMMS register gives condition and the responsible person (looked up in HR); work orders give history."""
    staff = {s["EMPLOYEE_ID"]: s for s in _read_csv(SOURCES / "staff" / "hr_directory.csv")}
    for r in _read_csv(SOURCES / "maintenance" / "asset_register.csv"):
        a = assets[r["EQUIP_NO"]]
        a.condition_rating = int(r["CONDITION_RATING"])
        a.sources.append("cmms")
        s = staff.get(r["OWNER_EMPLOYEE_ID"])
        if s:
            a.owner = Owner(employee_id=s["EMPLOYEE_ID"], name=f"{s['FIRST_NAME']} {s['LAST_NAME']}",
                            title=s["JOB_TITLE"], team=s["TEAM"], email=s["EMAIL"], phone=s["WORK_PHONE"])
            a.sources.append("hr")

    for w in _read_csv(SOURCES / "maintenance" / "work_orders.csv"):
        # history = anything that says something about failure risk; routine PM is left out
        if w["WO_TYPE"] in ("CM", "STORM") or w["FAILURE_CODE"]:
            assets[w["EQUIP_NO"]].history.append(HistoryItem(
                date=date.fromisoformat(w["REPORTED"]), wo_no=w["WO_NO"], type=w["WO_TYPE"], summary=w["DESCRIPTION"],
                failure_code=w["FAILURE_CODE"], storm_event=w["STORM_EVENT"], cost_usd=float(w["COST_USD"] or 0)))
    for a in assets.values():
        a.history.sort(key=lambda h: h.date, reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def aggregate() -> dict[str, AggregatedData]:
    """Aggregate data from different sources into a clean data obj keyed by assetID (baseline, no field events)."""
    assets = _load_gis()
    _add_dependencies(assets)
    _add_facilities(assets)
    _add_maintenance(assets)
    return assets


def save(path: Path = PROCESSED) -> Path:
    """Batch job: write the baseline for everything else to read.

    Run once for the demo; in production this runs on a schedule (e.g. nightly), while field events
    arrive in real time and are layered on with apply_field_events().
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"assets": [a.model_dump(mode="json") for a in aggregate().values()]}, indent=2))
    return path

@lru_cache
def load_processed_assets(path: Path = PROCESSED) -> dict[str, AggregatedData]:
    """Read the baseline written by save()."""
    return {a["asset_id"]: AggregatedData.model_validate(a) for a in json.loads(path.read_text())["assets"]}


def load_staff() -> list[Owner]:
    """Everyone in the HR directory."""
    return [Owner(employee_id=s["EMPLOYEE_ID"], name=f"{s['FIRST_NAME']} {s['LAST_NAME']}", title=s["JOB_TITLE"],
                  team=s["TEAM"], email=s["EMAIL"], phone=s["WORK_PHONE"])
            for s in _read_csv(SOURCES / "staff" / "hr_directory.csv")]


def on_call(role: str, at: datetime) -> Owner | None:
    """Who holds an on-call role at a given time, e.g. on_call("Emergency Manager on duty", advisory.issued_at)."""
    staff = {s["EMPLOYEE_ID"]: s for s in _read_csv(SOURCES / "staff" / "hr_directory.csv")}
    for r in _read_csv(SOURCES / "staff" / "on_call_roster.csv"):
        start, end = datetime.fromisoformat(r["start"]), datetime.fromisoformat(r["end"])
        if r["role"] == role and start <= at < end:
            s = staff[r["employee_id"]]
            return Owner(employee_id=s["EMPLOYEE_ID"], name=f"{s['FIRST_NAME']} {s['LAST_NAME']}",
                         title=s["JOB_TITLE"], team=s["TEAM"], email=s["EMAIL"], phone=s["WORK_PHONE"])
    return None


def apply_field_events(assets: dict[str, AggregatedData], as_of: datetime) -> dict[str, AggregatedData]:
    """Layer field app events received up to as_of (the replay clock) onto a copy of the baseline."""
    assets = {k: v.model_copy(deep=True) for k, v in assets.items()}
    with open(SOURCES / "field_ops" / "events.jsonl") as f:
        events = sorted((json.loads(line) for line in f if line.strip()), key=lambda e: e["received_at"])
    for ev in events:
        received = datetime.fromisoformat(ev["received_at"])
        if received > as_of or ev["asset_id"] is None:
            continue  # not received yet, or a crew-level event with no asset
        a = assets[ev["asset_id"]]
        a.field_events.append(FieldEvent(event_id=ev["event_id"], received_at=received, event_type=ev["event_type"],
                                         status=ev["status"], notes=ev["notes"], crew_id=ev["crew_id"]))
        a.status = ev["status"]
        if "field_ops" not in a.sources:
            a.sources.append("field_ops")
    return assets


@lru_cache
def _advisories_file() -> dict:
    """All Ian advisories in one FeatureCollection (read once, then cached)."""
    return json.loads((WEATHER / "advisories.geojson").read_text())


def load_advisory_index() -> list[dict]:
    """Hurricane Ian advisories in replay order (advisory number, issued_at, centre, max wind, category)."""
    return _advisories_file()["properties"]["advisories"]


def load_advisory_features(advisory: int) -> list[dict]:
    """All GeoJSON features of one advisory (cone, track, forecast points, wind zones, warnings), for the map."""
    return [f for f in _advisories_file()["features"] if f["properties"]["advisory"] == advisory]


def load_advisory(advisory: int) -> Advisory:
    """One NHC advisory: issue time, storm centre and strength, and its wind zones (now and forecast)."""
    meta = next(m for m in load_advisory_index() if m["advisory"] == advisory)
    zones = [WindZone(threshold_kt=f["properties"]["threshold_kt"], hours_ahead=f["properties"]["tau_hours"],
                      geometry=f["geometry"])
             for f in _advisories_file()["features"]
             if f["properties"]["advisory"] == advisory and f["properties"]["layer"] == "wind_radii"]
    return Advisory(advisory=meta["advisory"], issued_at=meta["issued_at"], center=Location(**meta["center"]),
                    max_wind_kt=meta["max_wind_kt"], category=meta["saffir_simpson"], wind_zones=zones)

