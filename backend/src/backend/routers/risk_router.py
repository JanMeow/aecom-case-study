"""Risk scores and the alert rules that act on them."""
from collections import Counter

from fastapi import APIRouter, HTTPException

from backend.api.model import AlertsResponse, AssetRisk, RiskResponse
from backend.ETL.alerts import alerts_until, scores_for
from backend.ETL.extraction import apply_field_events, load_advisory
from backend.ETL.threshold import TIERS
from backend.routers.shared import ASSETS, check_advisory

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


@router.get("/alerts")
def get_alerts(advisory: int, mode: str = "standard") -> AlertsResponse:
    """Messages sent and incident room status up to this advisory. mode: which score drives the rules."""
    check_advisory(advisory)
    if mode not in ("standard", "ml"):
        raise HTTPException(400, "mode must be 'standard' or 'ml'")
    alerts, room = alerts_until(advisory, mode)
    return AlertsResponse(advisory=advisory, mode=mode, alerts=alerts, room=room)
