"""Response shapes for the API (what the frontend receives)."""
from datetime import datetime
from pydantic import BaseModel
from backend.ETL.model import Alert, IncidentRoom, Location, RiskResult
from typing import Optional


class AssetSummary(BaseModel):
    """One row of the asset list: enough to draw a marker and a label on the map."""
    asset_id: str
    name: str
    type: str
    region: str
    location: Location
    path: list[tuple[float, float]] | None = None   # (lon, lat) route, transmission lines only
    upstream: list[str] = []                         # asset IDs it depends on
    downstream: list[str] = []                       # asset IDs that depend on it


class AssetRisk(BaseModel):
    """Both scores for one asset, side by side."""
    asset_id: str
    standard: RiskResult     # rules mode
    ml: RiskResult           # ML mode (same likelihood/consequence steps, ML own chance)
    field_status: str | None = None   # latest field crew report at advisory time, e.g. "out", "on_generator"


class RiskResponse(BaseModel):
    advisory: int
    issued_at: datetime
    tiers: dict[str, dict[str, int]]   # mode -> tier -> number of assets, e.g. {"standard": {"Critical": 1, ...}}
    results: list[AssetRisk]           # highest standard score first


class AdvisorySummary(BaseModel):
    """One step of the replay timeline."""
    advisory: int
    issued_at: datetime
    issued_label: str          # as NHC wrote it, e.g. "1100 PM EDT Tue Sep 27 2022"
    center: Location           # storm centre at issue time
    max_wind_kt: int
    category: int              # Saffir-Simpson, 0 = tropical storm
    storm_type: str            # e.g. "Major Hurricane"


class AdvisoryMap(BaseModel):
    """One advisory as GeoJSON, ready for the map (MapLibre can add it as a source directly).

    Each feature has properties.layer:
        cone            where the storm centre may go (5-day forecast)
        track           forecast path of the centre
        forecast_point  centre position every 12-24 h, with forecast wind
        wind_radii      areas with winds >= 34 / 50 / 64 kt (kind: current or forecast, tau_hours ahead)
        watch_warning   coastal hurricane / tropical storm watches and warnings
    """
    type: str = "FeatureCollection"
    properties: AdvisorySummary
    features: list[dict]


class AlertsResponse(BaseModel):
    """What the alert rules have done up to this advisory (replayed from the start, so the slider can go back)."""
    advisory: int
    mode: str                          # standard | ml: which score drove the alerts
    alerts: list[Alert]                # oldest first
    room: IncidentRoom | None          # None until an asset first reaches Critical


# ---------------------------------------------------------------------------
# AI requests (incident room commands)
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    """Plain message in the incident room."""
    advisory: int
    question: str
    conversation:Optional[list[str]] #In the future might send over the prevous conversation for context


class ReportRequest(BaseModel):
    """/generate_report [asset]: situation briefing; asset defaults to the room's trigger asset."""
    advisory: int
    asset_id: str | None = None


class PlaybookRequest(BaseModel):
    """/playbook [asset] question: what the playbooks say for one asset."""
    asset_id: str
    question: str
