"""Data models for computer vision on satellite imagery (CV/)."""
from pydantic import BaseModel


class GreenCover(BaseModel):
    """Share of an image that is vegetation, measured from pixel colours."""
    green_pct: float        # 0..100: share of pixels counted as vegetation (includes grass, not only trees)
    threshold: float        # Excess Green value above which a pixel counts, chosen by Otsu's method
    mask_png: bytes         # the image with counted pixels highlighted, to show what was measured


class CanopyInference(BaseModel):
    """What the vision model reads from the image: tree canopy as opposed to all green (e.g. grass)."""
    tree_canopy_pct: int    # 0..100: share of the image covered by tree canopy, as estimated by the model
    confidence: str         # low | medium | high
    notes: str              # e.g. "mature trees along the east fence, within ~10 m of the switchyard"
