"""
calculate the risk scoring using
1. Standard risk formula
2. ML basd method

Standard (rules) formula:  risk = likelihood x consequence

    1. wind zone     which wind zone (34 / 50 / 64 kt) is the asset in now, and which is forecast?
    2. own chance    lookup table (asset type x wind zone) x condition, + flood bonus;
                     a forecast zone counts 75%, and the worse of now / forecast is used
    3. likelihood    max(own chance, likelihood of what it depends on); a backup generator halves power risk
    4. consequence   customers affected (own + downstream) + critical facilities, 0..1
    5. score         likelihood x (0.5 + 0.5 x consequence) -> tier

All settings live in threshold.py. Every step is kept in the RiskResult so the UI and AI can explain it.
"""

from shapely.geometry import Point, shape

from backend.ETL.model import Advisory, AggregatedData, Consequence, Likelihood, OwnChance, RiskResult
from backend.ETL.threshold import (BACKUP_GENERATOR_FACTOR, BASE_CHANCE, CONDITION_MULTIPLIER, CONSEQUENCE_FLOOR,
                                   CRITICAL_FACILITY_BONUS, CUSTOMERS_FOR_MAX, DEFAULT_CONDITION, FLOOD_BONUS,
                                   FLOOD_ZONES, FORECAST_MAX_HOURS, FORECAST_WEIGHT, TIERS)
from backend.ML.train_predict import get_model, predict


# ---------------------------------------------------------------------------
# 1. Wind zone
# ---------------------------------------------------------------------------
def wind_zones(asset: AggregatedData, advisory: Advisory) -> tuple[int, int]:
    """Which wind zones is the asset in? This is the storm's side of the score.

    An NHC advisory has polygons for winds of at least 34, 50 and 64 kt, for now and for the coming hours.
    Returns (now_kt, forecast_kt): the strongest zone containing the asset now, and the strongest zone forecast
    to contain it. 0 means outside every zone.

    Thresholds (threshold.py):
        FORECAST_MAX_HOURS  only forecasts up to this many hours ahead count (currently 36)
    """
    point = Point(asset.location.lon, asset.location.lat)
    now, soon = 0, 0
    for z in advisory.wind_zones:
        # Check if current asset is in the wind zone
        if shape(z.geometry).contains(point):
            if z.hours_ahead == 0:
                now = max(now, z.threshold_kt)
            elif z.hours_ahead <= FORECAST_MAX_HOURS:
                soon = max(soon, z.threshold_kt)
    return now, soon


# ---------------------------------------------------------------------------
# 2. Own chance of failing
# ---------------------------------------------------------------------------
def _chance(asset: AggregatedData, zone_kt: int) -> tuple[float, float, float, float]:
    """Chance this asset fails in one wind zone, ignoring everything it depends on.

        chance = BASE_CHANCE[type][zone] x CONDITION_MULTIPLIER[rating] + FLOOD_BONUS (if flood-prone), capped at 1

    Flood bonus: hurricanes push seawater inland (storm surge), worst near the eye, i.e. in the 64 kt zone.
    Assets in FEMA flood zones AE or VE are low-lying areas that flood first, so in the 64 kt zone they
    get a higher chance of failing on top of the wind damage.

    Thresholds (threshold.py):
        BASE_CHANCE           chance by asset type and wind zone, e.g. substation in 64 kt zone = 50%
        CONDITION_MULTIPLIER  maintenance rating 1 (excellent) .. 5 (very poor), e.g. rating 4 -> x1.3
        DEFAULT_CONDITION     rating used when an asset has none (3 -> x1.0)
        FLOOD_ZONES           FEMA zones treated as flood-prone ("AE", "VE")
        FLOOD_BONUS           added in the 64 kt zone for those assets (+0.30)

    Returns (chance, base_chance, condition_multiplier, flood_bonus).
    """
    if zone_kt == 0:
        return 0.0, 0.0, 1.0, 0.0
    base = BASE_CHANCE[asset.type][zone_kt]
    multiplier = CONDITION_MULTIPLIER[asset.condition_rating or DEFAULT_CONDITION]
    flood = FLOOD_BONUS if zone_kt == 64 and asset.flood_zone in FLOOD_ZONES else 0.0
    return min(1.0, base * multiplier + flood), base, multiplier, flood


def own_chance(asset: AggregatedData, now_kt: int, forecast_kt: int) -> OwnChance:
    """STEP 2 - OWN CHANCE: how likely this asset is to fail by itself, from the storm hitting it directly
    (wind, flooding, its own condition). It ignores upstream assets; likelihood() adds those.

    Worked out for the zone it is in now and for the forecast zone; the forecast counts less because it
    has not arrived yet and may change. The worse of the two is used, so alerts can fire before landfall.

        own_chance = max(_chance(now zone), _chance(forecast zone) x FORECAST_WEIGHT)

    e.g. SUB-014 in the 64 kt zone now: 50% x 1.3 (condition 4) + 30% (flood zone AE) = 95%
         same zone only forecast:       95% x 0.75 = 71%

    Thresholds (threshold.py):
        FORECAST_WEIGHT  share a forecast zone counts for (0.75)
        plus everything _chance() uses
    """
    now, base_now, mult_now, flood_now = _chance(asset, now_kt)
    soon, base_soon, mult_soon, flood_soon = _chance(asset, forecast_kt)
    if soon * FORECAST_WEIGHT > now:
        return OwnChance(chance=soon * FORECAST_WEIGHT, zone_kt=forecast_kt, forecast=True,
                         base_chance=base_soon, condition_multiplier=mult_soon, flood_bonus=flood_soon)
    return OwnChance(chance=now, zone_kt=now_kt, forecast=False,
                     base_chance=base_now, condition_multiplier=mult_now, flood_bonus=flood_now)


def ml_own_chance(assets: dict[str, AggregatedData], zones: dict[str, tuple[int, int]]) -> dict[str, OwnChance]:
    """STEP 2, ML version: the own chance comes from the ML model (ML/train_predict.py) instead of the table.

    zones: asset_id -> (now_kt, forecast_kt) from step 1.
    Same rule as the rules version: ask about the zone now and the forecast zone, the forecast counts
    FORECAST_WEIGHT (0.75), and the worse of the two is used. Done for all assets at once (one model call).
    """
    model = get_model()
    now = predict(model, assets, {a: z[0] for a, z in zones.items()})
    soon = predict(model, assets, {a: z[1] for a, z in zones.items()})

    own = {}
    for asset_id in assets:
        now_kt, forecast_kt = zones[asset_id]
        (p_now, why_now), (p_soon, why_soon) = now[asset_id], soon[asset_id]
        if not now_kt and not forecast_kt:
            own[asset_id] = OwnChance(chance=0.0, zone_kt=0, forecast=False)
        elif forecast_kt and p_soon * FORECAST_WEIGHT > p_now:
            own[asset_id] = OwnChance(chance=p_soon * FORECAST_WEIGHT, zone_kt=forecast_kt, forecast=True,
                                      why=[f"ML: chance {p_soon:.0%} x {FORECAST_WEIGHT} (forecast)"] + why_soon)
        else:
            own[asset_id] = OwnChance(chance=p_now, zone_kt=now_kt, forecast=False,
                                      why=[f"ML: chance {p_now:.0%}"] + why_now)
    return own


# ---------------------------------------------------------------------------
# 3. Likelihood: an asset is at least as likely to fail as what it depends on
# ---------------------------------------------------------------------------
def likelihood(asset_id: str, assets: dict[str, AggregatedData], own: dict[str, OwnChance],
               cache: dict[str, Likelihood]) -> Likelihood:
    """STEP 3 - LIKELIHOOD: how likely the asset is to fail, now including UPSTREAM (what it depends on).

    An asset is at least as likely to fail as what it depends on: a pumping station with no power stops
    even if the storm doesn't touch it.

        likelihood = max(own chance, likelihood of each upstream asset)

    Walks up asset.upstream recursively, so risk flows down the chain:
    TL-008 (84%) -> SUB-014 inherits 84% if its own chance is lower -> PS-007 inherits it next.
    cache keeps each asset's answer so the chain is only walked once.

    Thresholds (threshold.py):
        BACKUP_GENERATOR_FACTOR  a failed power supply counts only this share if the asset has a generator (0.5)
    """
    if asset_id in cache:
        return cache[asset_id]
    asset = assets[asset_id]
    best = Likelihood(value=own[asset_id].chance)
    cache[asset_id] = best                      # guards against a loop in bad data
    for link in asset.upstream:
        inherited = likelihood(link.asset_id, assets, own, cache).value
        if link.type == "power" and asset.has_backup_power:
            inherited *= BACKUP_GENERATOR_FACTOR
        if inherited > best.value:
            best = Likelihood(value=inherited, depends_on=link.asset_id)
    cache[asset_id] = best
    return best


# ---------------------------------------------------------------------------
# 4. Consequence: who is affected if it fails?
# ---------------------------------------------------------------------------
def get_downstream(assets: dict[str, AggregatedData], asset_id: str) -> set[str]:
    """The asset plus everything DOWNSTREAM of it (everything that depends on it, directly or indirectly).

    e.g. SUB-014 -> WTP-002, WWTP-003, PS-007, PS-017 -> and what depends on those in turn.
    """
    seen, todo = set(), [asset_id]
    while todo:
        current = todo.pop()
        if current not in seen:
            seen.add(current)
            todo.extend(assets[current].downstream)
    return seen


def consequence(assets: dict[str, AggregatedData], asset_id: str) -> Consequence:
    """STEP 4 - CONSEQUENCE: how bad it is if this asset fails, counting everything DOWNSTREAM that goes down with it.

        consequence = customers affected / CUSTOMERS_FOR_MAX + CRITICAL_FACILITY_BONUS x facilities, capped at 1

    e.g. SUB-014: 246,000 / 500,000 + 0.1 x 5 facilities = 0.99
         PS-007:   28,000 / 500,000 + 0.1 x 3 facilities = 0.36

    Thresholds (threshold.py):
        CUSTOMERS_FOR_MAX        customers affected that alone give the maximum consequence of 1.0 (500,000);
                                 an asset affecting 250,000 customers scores 0.5 from customers
        CRITICAL_FACILITY_BONUS  added per hospital, shelter, EOC or nursing home affected (0.1)
    """
    affected = [assets[a] for a in get_downstream(assets, asset_id)]
    customers = sum(a.customers_served for a in affected)
    facilities = sorted({f.facility_id for a in affected for f in a.critical_facilities})
    value = min(1.0, customers / CUSTOMERS_FOR_MAX + CRITICAL_FACILITY_BONUS * len(facilities))
    return Consequence(value=value, customers=customers, facilities=facilities)


# ---------------------------------------------------------------------------
# 5. Score, tier and explanation
# ---------------------------------------------------------------------------
def final_score(lik: Likelihood, cons: Consequence) -> tuple[float, str]:
    """STEP 5 - SCORE AND TIER.

        score = likelihood x (CONSEQUENCE_FLOOR + (1 - CONSEQUENCE_FLOOR) x consequence)

    e.g. SUB-014: 0.95 x (0.5 + 0.5 x 0.99) = 0.95 -> Critical
         PS-007:  0.95 x (0.5 + 0.5 x 0.36) = 0.64 -> High   (same likelihood, smaller consequence)

    Thresholds (threshold.py):
        CONSEQUENCE_FLOOR  lowest share of likelihood kept when consequence is 0 (0.5), so a certain failure
                           of even the smallest asset still scores 0.5 (High)
        TIERS              score -> tier: >= 0.75 Critical (open incident room), >= 0.50 High (notify owner),
                           >= 0.25 Medium, else Low
    """
    score = lik.value * (CONSEQUENCE_FLOOR + (1 - CONSEQUENCE_FLOOR) * cons.value)
    return score, next(tier for threshold, tier in TIERS if score >= threshold)


def build_explanation(asset: AggregatedData, own: OwnChance, lik: Likelihood, cons: Consequence) -> list[str]:
    """Plain-English reasons, one per step that mattered, e.g.
    ["Substation in 64 kt wind zone (now): base chance 50%", "Condition 4/5: x1.3", "Flood zone AE: +30%",
     "Depends on TL-008 (84% likely to fail)", "Affects 246,000 customers and 5 critical facilities"]
    """
    reasons = []
    if own.zone_kt and own.base_chance is not None:            # rules: show the arithmetic
        when = "forecast" if own.forecast else "now"
        reasons.append(f"{asset.type.replace('_', ' ').capitalize()} in {own.zone_kt} kt wind zone ({when}): "
                       f"base chance {own.base_chance:.0%}")
        if own.condition_multiplier != 1.0:
            reasons.append(f"Condition {asset.condition_rating}/5: x{own.condition_multiplier}")
        if own.flood_bonus:
            reasons.append(f"Flood zone {asset.flood_zone}: +{own.flood_bonus:.0%}")
    elif own.zone_kt:                                          # ML: what the model says drove it
        when = "forecast" if own.forecast else "now"
        reasons.append(f"{own.zone_kt} kt wind zone ({when})")
        reasons.extend(own.why)
    if lik.depends_on:
        reasons.append(f"Depends on {lik.depends_on} ({lik.value:.0%} likely to fail)")
    reasons.append(f"Affects {cons.customers:,} customers and {len(cons.facilities)} critical facilities")
    return reasons


def to_result(asset: AggregatedData, own: OwnChance, lik: Likelihood, cons: Consequence, mode: str) -> RiskResult:
    """STEP 5 for one asset: final score and tier, the explanation, and every step's numbers in one RiskResult."""
    score, tier = final_score(lik, cons)
    return RiskResult(
        asset_id=asset.asset_id, mode=mode, score=round(score, 3), tier=tier,
        wind_zone_kt=own.zone_kt, forecast=own.forecast, base_chance=own.base_chance,
        condition_multiplier=own.condition_multiplier, flood_bonus=own.flood_bonus, own_chance=round(own.chance, 3),
        depends_on=lik.depends_on, likelihood=round(lik.value, 3), customers_affected=cons.customers,
        critical_facilities=cons.facilities, consequence=round(cons.value, 3),
        reasons=build_explanation(asset, own, lik, cons))


# ---------------------------------------------------------------------------
# Entry points: the five steps, one line each
# ---------------------------------------------------------------------------
def standard_risk_score(assets: dict[str, AggregatedData], advisory: Advisory) -> dict[str, RiskResult]:
    """Score every asset against one advisory, rules version.

    Each step runs for every asset before the next one starts. Order matters only for step 3: an asset
    inherits risk from what it depends on, so every asset's own chance (step 2) must exist first.
    """
    # 1. Which wind zones is each asset in (now and forecast)?
    zones = {a: wind_zones(asset, advisory) for a, asset in assets.items()}
    # 2. How likely is each asset to fail by itself?
    own = {a: own_chance(assets[a], *zones[a]) for a in assets}
    # 3. Could it fail because something it depends on fails?  (needs step 2 for every asset)
    cache: dict[str, Likelihood] = {}
    lik = {a: likelihood(a, assets, own, cache) for a in assets}
    # 4. How bad would it be if it failed?
    cons = {a: consequence(assets, a) for a in assets}
    # 5. Score, tier and explanation
    return {a: to_result(assets[a], own[a], lik[a], cons[a], "rules") for a in assets}

def ml_risk_score_for_zones(assets: dict[str, AggregatedData], zones: dict[str, tuple[int, int]]) -> dict[str, RiskResult]:
    """Steps 2-5 (ML) given each asset's (now_kt, forecast_kt), wherever the zones come from:
    a real advisory (ml_risk_score) or a what-if scenario (ml_simulate_risk_score)."""
    # 2. How likely is each asset to fail by itself?  (ML model instead of the lookup table)
    own = ml_own_chance(assets, zones)
    # 3. Could it fail because something it depends on fails?
    cache: dict[str, Likelihood] = {}
    lik = {a: likelihood(a, assets, own, cache) for a in assets}
    # 4. How bad would it be if it failed?
    cons = {a: consequence(assets, a) for a in assets}
    # 5. Score, tier and explanation
    return {a: to_result(assets[a], own[a], lik[a], cons[a], "ml") for a in assets}


def ml_risk_score(assets: dict[str, AggregatedData], advisory: Advisory) -> dict[str, RiskResult]:
    """Same five steps as standard_risk_score; only step 2 (own chance) comes from the ML model,
    so the two scores can be compared like for like."""
    # 1. Which wind zones is each asset in (now and forecast)?
    zones = {a: wind_zones(asset, advisory) for a, asset in assets.items()}
    return ml_risk_score_for_zones(assets, zones)


def ml_simulate_risk_score(assets: dict[str, AggregatedData], wind_zone: int, region: str | None = None,
                           target: str | None = None) -> dict[str, RiskResult]:
    """What-if (scenario forecast): score every asset as if a storm with this wind zone hit, using the ML model.

    Step 1 is replaced by zones we choose; steps 2-5 are the same as for a real advisory. Who is hit:
        target only    target="PS-007"                 -> how fragile is this asset by itself
        a region       region="South" (+ target)       -> a realistic storm over an area, cascade included
        everywhere     region=None and target=None     -> the whole service area
    Everyone else gets no wind (0). Every asset is still scored, because step 3 reads the upstream assets.
    """
    def hit(asset: AggregatedData) -> bool:
        if asset.asset_id == target:
            return True
        if region is None:
            return target is None                  # no region and no target: the whole area is hit
        return asset.region == region

    # 1. Scenario: the chosen wind is here now for the assets hit (full weight, no forecast part), 0 elsewhere
    zones = {a: ((wind_zone if hit(asset) else 0), 0) for a, asset in assets.items()}
    return ml_risk_score_for_zones(assets, zones)
