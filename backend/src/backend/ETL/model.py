"""
Data models shared across the backend.

AggregatedData   one clean record per asset, built by extraction.aggregate() from all source systems
Advisory         one NHC hurricane advisory, built by extraction.load_advisory()
RiskResult       one asset's score from risk_score, with every step of the working for explanations
Alert, IncidentRoom  what the alert rules did (ETL/alerts.py)
"""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Aggregated asset data (extraction.py)
# ---------------------------------------------------------------------------
class Location(BaseModel):
    lat: float
    lon: float


class Owner(BaseModel):
    employee_id: str
    name: str
    title: str
    team: str
    email: str
    phone: str


class Link(BaseModel):
    asset_id: str
    type: str                 # power | water | wastewater


class CriticalFacility(BaseModel):
    facility_id: str
    name: str
    kind: str                 # hospital | shelter | emergency_operations | nursing_home
    via: str                  # power | water: what this asset supplies to it


class HistoryItem(BaseModel):
    date: date | None
    wo_no: str
    type: str                 # CM (corrective) | STORM | INSP
    summary: str
    failure_code: str = ""
    storm_event: str = ""
    cost_usd: float = 0


class FieldEvent(BaseModel):
    event_id: str
    received_at: datetime
    event_type: str
    status: str
    notes: str
    crew_id: str | None = None


class AggregatedData(BaseModel):
    asset_id: str
    name: str
    type: str
    region: str
    location: Location
    path: list[tuple[float, float]] | None = None   # (lon, lat) vertices, transmission lines only
    elevation_m: float
    flood_zone: str                                 # FEMA flood zone: VE (coastal, waves), AE (flood-prone), X (low risk)
    install_year: int
    customers_served: int
    condition_rating: int | None = None             # from CMMS; None if the asset is missing there
    has_backup_power: bool = False                  # standby generator on site
    backup_hours: float = 0                         # hours of generator fuel (for display and the AI)
    tree_canopy_pct: float | None = None            # ML feature only; the rules formula ignores it
    attributes: dict = Field(default_factory=dict)  # voltage_kv, capacity_mgd, service, ...
    owner: Owner | None = None
    upstream: list[Link] = Field(default_factory=list)
    downstream: list[str] = Field(default_factory=list)
    critical_facilities: list[CriticalFacility] = Field(default_factory=list)
    history: list[HistoryItem] = Field(default_factory=list)
    status: str | None = None                       # latest field status, e.g. "out", "on_generator"
    field_events: list[FieldEvent] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)  # systems that contributed to this record


# ---------------------------------------------------------------------------
# Hurricane advisory (extraction.load_advisory)
# ---------------------------------------------------------------------------
class WindZone(BaseModel):
    threshold_kt: int         # 34, 50 or 64: winds at least this strong inside the polygon
    hours_ahead: int          # 0 = now, 12 / 24 / 36 ... = forecast
    geometry: dict            # GeoJSON polygon


class Advisory(BaseModel):
    advisory: int             # NHC advisory number, e.g. 25
    issued_at: datetime
    center: Location          # storm centre at issue time
    max_wind_kt: int
    category: int             # Saffir-Simpson, 0 = tropical storm
    wind_zones: list[WindZone]


# ---------------------------------------------------------------------------
# Risk scoring steps (risk_score.py): one small result per step
# ---------------------------------------------------------------------------
class OwnChance(BaseModel):
    """Step 2: how likely the asset is to fail by itself."""
    chance: float                           # 0..1
    zone_kt: int                            # wind zone used (34 / 50 / 64, 0 = none)
    forecast: bool                          # True if that zone is forecast rather than here now
    base_chance: float | None = None        # rules only: lookup table value
    condition_multiplier: float | None = None   # rules only
    flood_bonus: float | None = None        # rules only
    why: list[str] = Field(default_factory=list)   # ML only: what the model says drove it


class Likelihood(BaseModel):
    """Step 3: own chance, or higher if something it depends on is more likely to fail."""
    value: float                            # 0..1
    depends_on: str | None = None           # the upstream asset that set it (None = its own chance)


class Consequence(BaseModel):
    """Step 4: how bad it is if the asset fails."""
    value: float                            # 0..1
    customers: int                          # own + everything downstream
    facilities: list[str] = Field(default_factory=list)   # critical facility IDs affected

type Mode = Literal["ml", "rules"]
# ---------------------------------------------------------------------------
# Risk scoring output (risk_score.py)
# ---------------------------------------------------------------------------
class RiskResult(BaseModel):
    asset_id: str
    mode: Mode = "rules"  # rules | ml: how own_chance was worked out
    score: float                            # likelihood x consequence factor
    tier: str                               # Low | Medium | High | Critical
    # likelihood: how likely the asset is to fail
    wind_zone_kt: int                       # 34 / 50 / 64, or 0 if outside all wind zones
    forecast: bool                          # True if the wind zone is forecast rather than here now
    base_chance: float | None = None        # rules only: lookup table, asset type x wind zone
    condition_multiplier: float | None = None   # rules only
    flood_bonus: float | None = None        # rules only
    own_chance: float                       # chance it fails by itself (rules formula or ML model)
    depends_on: str | None = None           # upstream asset whose failure risk is higher than its own
    likelihood: float                       # max(own chance, upstream likelihood)
    # consequence: how bad it is if it fails
    customers_affected: int                 # own + everything downstream
    critical_facilities: list[str] = Field(default_factory=list)
    consequence: float                      # 0..1
    reasons: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Alert rules output (alerts.py)
# ---------------------------------------------------------------------------
class Alert(BaseModel):
    advisory: int
    issued_at: datetime
    asset_id: str
    asset_name: str
    tier: str                               # High | Critical
    action: str                             # notify_owner | open_room | join_room
    recipients: list[Owner]
    message: str
    reasons: list[str] = Field(default_factory=list)


class IncidentRoom(BaseModel):
    opened_at: datetime
    opened_by_advisory: int
    trigger_asset: str                      # first asset to reach Critical
    critical_assets: list[str]
    members: list[Owner]
