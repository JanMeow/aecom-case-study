from collections import Counter

from fastapi import FastAPI, HTTPException

from .api.model import AdvisoryMap, AdvisorySummary, AlertsResponse, AssetRisk, AssetSummary, RiskResponse
from .ETL.alerts import alerts_until, scores_for
from .ETL.extraction import (apply_field_events, load_advisory, load_advisory_features, load_advisory_index,
                             load_processed_assets, load_staff)
from .ETL.model import AggregatedData, Owner
from .ETL.threshold import TIERS

#========================================
# Singleton data (the batch baseline, loaded once at startup)
#========================================
ASSETS = load_processed_assets()
ADVISORIES = {a["advisory"]: AdvisorySummary(category=a["saffir_simpson"], **a) for a in load_advisory_index()}

#========================================
# App
#========================================
app = FastAPI(title="SGW Resilience Platform")

#========================================
# Endpoints
#========================================
@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/assets")
def list_assets() -> list[AssetSummary]:
    """List all assets with the fields needed to draw them on the map."""
    return [AssetSummary(asset_id=a.asset_id, name=a.name, type=a.type, region=a.region, location=a.location,
                         path=a.path, upstream=[link.asset_id for link in a.upstream], downstream=a.downstream)
            for a in ASSETS.values()]


@app.get("/assets/{asset_id}")
def get_asset(asset_id: str) -> AggregatedData:
    """Full aggregated record of one asset: condition, owner, dependencies, facilities, history."""
    asset = ASSETS.get(asset_id)
    if asset is None:
        raise HTTPException(404, f"Asset {asset_id} not found")
    return asset


@app.get("/risks")
def get_risk(advisory: int) -> RiskResponse:
    """Score every asset against one advisory, in both modes (rules and ML), highest risk first."""
    if advisory not in ADVISORIES:
        raise HTTPException(404, f"Advisory {advisory} not found; available: {sorted(ADVISORIES)}")
    adv = load_advisory(advisory)
    standard, ml = scores_for(advisory, "standard"), scores_for(advisory, "ml")

    field = apply_field_events(ASSETS, adv.issued_at)   # what crews had reported by then
    results = sorted((AssetRisk(asset_id=a, standard=standard[a], ml=ml[a], field_status=field[a].status)
                      for a in ASSETS),
                     key=lambda r: -r.standard.score)
    tiers = {mode: {t: Counter(r.tier for r in scores.values())[t] for _, t in TIERS}
             for mode, scores in (("standard", standard), ("ml", ml))}
    return RiskResponse(advisory=adv.advisory, issued_at=adv.issued_at, tiers=tiers, results=results)


@app.get("/advisories")
def list_advisories() -> list[AdvisorySummary]:
    """Hurricane Ian advisories in replay order: the timeline the frontend steps through."""
    return list(ADVISORIES.values())


@app.get("/advisories/{advisory}/map")
def get_advisory_map(advisory: int) -> AdvisoryMap:
    """One advisory as GeoJSON: cone, track, forecast points, wind zones and warnings, for drawing the storm."""
    if advisory not in ADVISORIES:
        raise HTTPException(404, f"Advisory {advisory} not found; available: {sorted(ADVISORIES)}")
    return AdvisoryMap(properties=ADVISORIES[advisory], features=load_advisory_features(advisory))


@app.get("/alerts")
def get_alerts(advisory: int, mode: str = "standard") -> AlertsResponse:
    """Messages sent and incident room status up to this advisory. mode: which score drives the rules."""
    if advisory not in ADVISORIES:
        raise HTTPException(404, f"Advisory {advisory} not found; available: {sorted(ADVISORIES)}")
    if mode not in ("standard", "ml"):
        raise HTTPException(400, "mode must be 'standard' or 'ml'")
    alerts, room = alerts_until(advisory, mode)
    return AlertsResponse(advisory=advisory, mode=mode, alerts=alerts, room=room)


@app.get("/people")
def list_people() -> list[Owner]:
    """Staff directory, for the logged-in user switcher."""
    return load_staff()
