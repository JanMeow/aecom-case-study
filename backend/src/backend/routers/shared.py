"""Data every router uses, loaded once at startup (the batch baseline), and the common checks."""
from fastapi import HTTPException

from backend.api.model import AdvisorySummary
from backend.ETL.extraction import load_advisory_index, load_processed_assets
from backend.ETL.model import AggregatedData

ASSETS = load_processed_assets()
ADVISORIES = {a["advisory"]: AdvisorySummary(category=a["saffir_simpson"], **a) for a in load_advisory_index()}


def check_advisory(advisory: int) -> None:
    """404 if the advisory number isn't in the replay."""
    if advisory not in ADVISORIES:
        raise HTTPException(404, f"Advisory {advisory} not found; available: {sorted(ADVISORIES)}")


def check_asset(asset_id: str) -> AggregatedData:
    """The asset's aggregated record, or 404."""
    if asset_id not in ASSETS:
        raise HTTPException(404, f"Asset {asset_id} not found")
    return ASSETS[asset_id]
