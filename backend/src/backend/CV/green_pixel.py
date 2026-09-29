import io
import numpy as np
from PIL import Image
from backend.CV.model import GreenCover

# Otsu's threshold is kept inside this Excess Green band (vegetation typically scores 0.05-0.3)
EXG_THRESHOLD_RANGE = (0.03, 0.15)



def count_green_cover(png: bytes) -> GreenCover:
    """Share of the image that is vegetation, measured from pixel colours (no model, no API).

    1. Excess Green on normalised colours: r = R/(R+G+B) etc., ExG = 2g - r - b. Normalising removes most of the
       brightness effect, so sunlit and shaded leaves score alike. Vegetation is roughly ExG > 0.05.
    2. Threshold chosen per image by Otsu's method: the value that best splits the ExG histogram into two groups
       (vegetation vs everything else), so no hand-picked colour range.
    3. Otsu assumes both groups are present; on an almost all-green or all-grey tile it would split noise,
       so the threshold is clamped to EXG_THRESHOLD_RANGE.

    Counts grass as well as trees: report it as "green cover", and leave trees vs grass to the vision model.
    """
    rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float64)
    total = rgb.sum(axis=2) + 1e-6                       # avoid dividing by zero on black pixels
    r, g, b = (rgb[..., i] / total for i in range(3))
    exg = 2 * g - r - b

    lo, hi = EXG_THRESHOLD_RANGE
    threshold = float(np.clip(_otsu(exg), lo, hi))
    green = exg > threshold
    return GreenCover(green_pct=round(100 * green.mean(), 1), threshold=round(threshold, 3),
                      mask_png=_highlight(rgb, green))


def _otsu(values: np.ndarray, bins: int = 256) -> float:
    """Otsu's method: the threshold that maximises the variance between the two groups it creates."""
    hist, edges = np.histogram(values, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2
    weight_low = np.cumsum(hist)                          # pixels at or below each candidate threshold
    weight_high = weight_low[-1] - weight_low
    sum_low = np.cumsum(hist * centres)
    mean_low = sum_low / np.maximum(weight_low, 1)
    mean_high = (sum_low[-1] - sum_low) / np.maximum(weight_high, 1)
    between = weight_low * weight_high * (mean_low - mean_high) ** 2
    return float(centres[np.argmax(between)])


def _highlight(rgb: np.ndarray, mask: np.ndarray) -> bytes:
    """The photo, greyed out except the counted pixels, which are tinted bright green: shows what was measured."""
    grey = rgb.mean(axis=2, keepdims=True).repeat(3, axis=2) * 0.6
    out = np.where(mask[..., None], rgb * 0.4 + np.array([0, 255, 90]) * 0.6, grey)
    buf = io.BytesIO()
    Image.fromarray(out.astype(np.uint8)).save(buf, format="PNG")
    return buf.getvalue()

