"""Computer vision on satellite imagery: tree canopy around an asset."""
import base64

from fastapi import APIRouter

from backend.api.model import CanopyRequest, CanopyResponse
from backend.CV.esri import ESRI_ATTRIBUTION, get_satellite_image
from backend.CV.green_pixel import count_green_cover
from backend.CV.inference import claude_inference
from backend.routers.shared import check_asset, check_model

router = APIRouter(prefix="/cv", tags=["cv"])

_CANOPY: dict[tuple[str, str], CanopyResponse] = {}   # (asset_id, model) -> result; imagery doesn't change
_SIZE_M = {"transmission_line": 800}        # area shown (m); lines are long, so a wider view of their midpoint
_DEFAULT_SIZE_M = 300


def _data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


@router.post("/tree_canopy_pct")
async def infer_tree_canopy_pct(req: CanopyRequest) -> CanopyResponse:
    """Satellite image of the asset's surroundings -> measured green cover -> Claude's tree canopy estimate."""
    asset = check_asset(req.asset_id)
    model = check_model(req.model)
    key = (req.asset_id, model)
    if key not in _CANOPY:
        size_m = _SIZE_M.get(asset.type, _DEFAULT_SIZE_M)
        png = await get_satellite_image(asset.location.lat, asset.location.lon, size_m=size_m)
        green = count_green_cover(png)
        ai = await claude_inference(png, green.green_pct, asset, size_m, model=model)
        _CANOPY[key] = CanopyResponse(
            asset_id=req.asset_id, gis_tree_canopy_pct=asset.tree_canopy_pct, green_pct=green.green_pct,
            threshold=green.threshold, ai=ai, image=_data_url(png), mask=_data_url(green.mask_png),
            size_m=size_m, attribution=ESRI_ATTRIBUTION, model=model)
    return _CANOPY[key]
