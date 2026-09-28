"""Hurricane Ian advisories: the replay timeline and the storm shapes for the map."""
from fastapi import APIRouter

from backend.api.model import AdvisoryMap, AdvisorySummary
from backend.ETL.extraction import load_advisory_features
from backend.routers.shared import ADVISORIES, check_advisory

router = APIRouter(prefix="/advisories", tags=["advisories"])


@router.get("")
def list_advisories() -> list[AdvisorySummary]:
    """Hurricane Ian advisories in replay order: the timeline the frontend steps through."""
    return list(ADVISORIES.values())


@router.get("/{advisory}/map")
def get_advisory_map(advisory: int) -> AdvisoryMap:
    """One advisory as GeoJSON: cone, track, forecast points, wind zones and warnings, for drawing the storm."""
    check_advisory(advisory)
    return AdvisoryMap(properties=ADVISORIES[advisory], features=load_advisory_features(advisory))
