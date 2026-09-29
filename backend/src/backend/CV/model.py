"""Data models for computer vision on satellite imagery (CV/)."""
from typing import Literal

from pydantic import BaseModel, Field


class GreenCover(BaseModel):
    """Share of an image that is vegetation, measured from pixel colours."""
    green_pct: float        # 0..100: share of pixels counted as vegetation (includes grass, not only trees)
    threshold: float        # Excess Green value above which a pixel counts, chosen by Otsu's method
    mask_png: bytes         # the image with counted pixels highlighted, to show what was measured


class CanopyInference(BaseModel):
    """What the vision model reads from the image: tree canopy as opposed to all green (e.g. grass).
    Used as the structured output schema, so the field descriptions guide the model."""
    tree_canopy_pct: int = Field(ge=0, le=100, description="Share of the whole image covered by tree canopy only "
                                                           "(not grass or fields), 0-100")
    confidence: Literal["low", "medium", "high"] = Field(description="How sure the estimate is")
    notes: str = Field(description="One or two sentences: trees close to equipment, buildings or lines, and "
                                   "whether the image shows the expected kind of site")
