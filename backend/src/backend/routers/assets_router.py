"""Assets: the aggregated view of every source system."""
from fastapi import APIRouter

from backend.api.model import AssetSummary
from backend.ETL.model import AggregatedData
from backend.routers.shared import ASSETS, check_asset

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
def list_assets() -> list[AssetSummary]:
    """List all assets with the fields needed to draw them on the map."""
    return [AssetSummary(asset_id=a.asset_id, name=a.name, type=a.type, region=a.region, location=a.location,
                         path=a.path, upstream=[link.asset_id for link in a.upstream], downstream=a.downstream)
            for a in ASSETS.values()]


@router.get("/{asset_id}")
def get_asset(asset_id: str) -> AggregatedData:
    """Full aggregated record of one asset: condition, owner, dependencies, facilities, history."""
    return check_asset(asset_id)
