"""Risk scores and the alert rules that act on them."""
from collections import Counter
from typing import Literal

from fastapi import APIRouter, HTTPException

from backend.api.model import AlertsResponse, AssetRisk, ForecastResponse, RiskResponse
from backend.ETL.alerts import alerts_until, scores_for
from backend.ETL.extraction import apply_field_events, load_advisory
from backend.ETL.threshold import TIERS
from backend.ETL.risk_score import ml_simulate_risk_score
from backend.routers.shared import ASSETS, check_advisory, check_asset

router = APIRouter(tags=["risk"])


@router.get("/risks")
def get_risk(advisory: int) -> RiskResponse:
    """Score every asset against one advisory, in both modes (rules and ML), highest risk first."""
    check_advisory(advisory)
    adv = load_advisory(advisory)
    standard, ml = scores_for(advisory, "standard"), scores_for(advisory, "ml")

    field = apply_field_events(ASSETS, adv.issued_at)   # what crews had reported by then
    results = sorted((AssetRisk(asset_id=a, standard=standard[a], ml=ml[a], field_status=field[a].status)
                      for a in ASSETS),
                     key=lambda r: -r.standard.score)
    tiers = {mode: {t: Counter(r.tier for r in scores.values())[t] for _, t in TIERS}
             for mode, scores in (("standard", standard), ("ml", ml))}
    return RiskResponse(advisory=adv.advisory, issued_at=adv.issued_at, tiers=tiers, results=results)



@router.get("/forecast")
def get_forecast(asset_id: str, wind_zone: int,
                 scope: Literal["asset", "region", "all"] = "region") -> ForecastResponse:
    """What-if: the asset's ML risk if a storm with this wind zone hit (34 / 50 / 64 kt).

    scope: asset = only this asset is hit (how fragile is it by itself);
           region = its whole region is hit (a realistic storm: its suppliers are hit too);
           all = the whole service area.
    """
    if wind_zone not in (34, 50, 64):
        raise HTTPException(400, "wind_zone must be 34, 50 or 64 (kt)")
    asset = check_asset(asset_id)
    region = asset.region if scope == "region" else None
    target = asset_id if scope != "all" else None
    results = ml_simulate_risk_score(ASSETS, wind_zone, region=region, target=target)
    hit = [r for r in results.values() if r.wind_zone_kt]
    tiers = {t: Counter(r.tier for r in results.values())[t] for _, t in TIERS}
    return ForecastResponse(asset_id=asset_id, wind_zone=wind_zone, scope=scope, region=region,
                            result=results[asset_id], assets_hit=len(hit), tiers=tiers)


@router.get("/alerts")
def get_alerts(advisory: int, mode: str = "standard") -> AlertsResponse:
    """Messages sent and incident room status up to this advisory. mode: which score drives the rules."""
    check_advisory(advisory)
    if mode not in ("standard", "ml"):
        raise HTTPException(400, "mode must be 'standard' or 'ml'")
    alerts, room = alerts_until(advisory, mode)
    return AlertsResponse(advisory=advisory, mode=mode, alerts=alerts, room=room)
