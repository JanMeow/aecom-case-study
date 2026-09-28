"""
Settings for the rules-based risk score (risk_score.py).

Plausible estimates in the style of FEMA Hazus damage tables, not calibrated engineering values.
Change a number here to tune the model; no code changes needed.
"""

# ---------------------------------------------------------------------------
# Likelihood: how likely is an asset to fail?
# ---------------------------------------------------------------------------
# Chance an asset fails, by asset type and the strongest wind zone it sits in (34 / 50 / 64 kt).
BASE_CHANCE = {
    "transmission_line":    {34: 0.10, 50: 0.30, 64: 0.65},   # long, exposed, trees fall on them
    "substation":           {34: 0.05, 50: 0.20, 64: 0.50},
    "pumping_station":      {34: 0.03, 50: 0.10, 64: 0.35},
    "wastewater_treatment": {34: 0.02, 50: 0.08, 64: 0.30},
    "water_treatment":      {34: 0.01, 50: 0.05, 64: 0.25},   # large, well-built sites
    "generation":           {34: 0.01, 50: 0.05, 64: 0.20},
}

# A forecast wind zone (not here yet) counts for this share, and only if it arrives within this many hours.
# The asset is scored on whichever is worse: the zone it is in now, or the weighted forecast zone.
FORECAST_WEIGHT = 0.75
FORECAST_MAX_HOURS = 36

# Maintenance condition rating (1 excellent .. 5 very poor) multiplies the chance.
CONDITION_MULTIPLIER = {1: 0.8, 2: 0.9, 3: 1.0, 4: 1.3, 5: 1.6}
DEFAULT_CONDITION = 3  # used when an asset has no rating

# Storm surge: assets in these FEMA flood zones get this added when they are in the 64 kt zone.
FLOOD_ZONES = {"VE", "AE"}
FLOOD_BONUS = 0.30

# A backup generator halves the risk passed down from a failed power supply.
BACKUP_GENERATOR_FACTOR = 0.5

# ---------------------------------------------------------------------------
# Consequence: how bad is it if the asset fails?
# ---------------------------------------------------------------------------
# consequence = customers affected / CUSTOMERS_FOR_MAX + CRITICAL_FACILITY_BONUS per facility, capped at 1
CUSTOMERS_FOR_MAX = 500_000
CRITICAL_FACILITY_BONUS = 0.1

# ---------------------------------------------------------------------------
# Score and tier
# ---------------------------------------------------------------------------
# score = likelihood x (CONSEQUENCE_FLOOR + (1 - CONSEQUENCE_FLOOR) x consequence)
# With 0.5, consequence can at most halve the score: a certain failure of a small asset still scores 0.5 (High).
CONSEQUENCE_FLOOR = 0.5

# Score -> tier. High notifies the asset owner; Critical opens an incident room.
TIERS = [(0.75, "Critical"), (0.50, "High"), (0.25, "Medium"), (0.0, "Low")]
