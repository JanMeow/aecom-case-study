"""Response shapes for the API (what the frontend receives)."""
from datetime import datetime
from pydantic import BaseModel
from backend.CV.model import CanopyInference
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
    conversation: Optional[list[str]] = None   # in the future: previous messages for context
    model: str | None = None                   # AI model; None = the default


class ReportRequest(BaseModel):
    """/generate_report [asset]: situation briefing; asset defaults to the room's trigger asset."""
    advisory: int
    asset_id: str | None = None
    model: str | None = None


class PlaybookRequest(BaseModel):
    """/playbook [asset] question: what the playbooks say for one asset."""
    asset_id: str
    question: str
    model: str | None = None


# ---------------------------------------------------------------------------
# Computer vision (tree canopy from satellite imagery)
# ---------------------------------------------------------------------------
class CanopyRequest(BaseModel):
    asset_id: str
    model: str | None = None


class CanopyResponse(BaseModel):
    """Tree canopy around an asset: GIS record vs what the imagery shows."""
    asset_id: str
    gis_tree_canopy_pct: float | None      # what the GIS record says
    green_pct: float                       # measured from pixel colours (Excess Green + Otsu); includes grass
    threshold: float
    ai: CanopyInference                    # the vision model's tree canopy estimate and notes
    image: str                             # satellite image, as a data URL (data:image/png;base64,...)
    mask: str                              # same image with the counted green pixels highlighted
    size_m: float                          # width of the area shown
    attribution: str                       # imagery credit, required by Esri
    model: str                             # model that made the AI estimate


class ModelOption(BaseModel):
    id: str                                # e.g. "claude-sonnet-5"
    label: str                             # e.g. "Sonnet 5 · balanced, faster"


# ---------------------------------------------------------------------------
# What-if scenario forecast (ML)
# ---------------------------------------------------------------------------
class ForecastResponse(BaseModel):
    """One asset's ML risk if a storm with this wind zone hit, and how the scenario looks overall."""
    asset_id: str
    wind_zone: int                         # 34 / 50 / 64 kt
    scope: str                             # asset | region | all: who the scenario hits
    region: str | None                     # the region hit, if scope is "region"
    result: RiskResult                     # the asset's ML score, tier and reasons under the scenario
    assets_hit: int
    tiers: dict[str, int]                  # tier -> number of assets across the scenario
