"""
Inference on the tree canopy in a satellite image.
Currently using claude, will use a segementation model in the future
"""
import base64
import json
import re

from backend.CV.model import CanopyInference
from backend.ETL.model import AggregatedData
from backend.LLM.service import _MODEL, client

_PROMPT = (
    "This is a satellite image about {size_m} m across, centred on {name}, a {type} of a power and water utility "
    "in Florida. A colour index measured {green_pct}% green cover in it, which includes grass as well as trees.\n"
    "1. Estimate the percentage of the whole image covered by tree canopy only (0-100), not grass or fields.\n"
    "2. Note any trees close to equipment, buildings or lines, which matter for storm damage.\n"
    "If the image doesn't show anything like a {type}, say so in the notes.\n"
    'Reply with JSON only: {{"tree_canopy_pct": <int>, "confidence": "low|medium|high", "notes": "<one or two sentences>"}}'
)


async def claude_inference(png: bytes, green_pct: float, asset: AggregatedData, size_m: float) -> CanopyInference:
    """Ask Claude to read tree canopy (as opposed to all green) from the image; returns its estimate and notes.

    The measured green % goes into the prompt so the model reasons about what that green is (trees or grass).
    The GIS canopy value is deliberately left out, so the estimate is an independent check on the records.
    """
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.b64encode(png).decode()}},
            {"type": "text", "text": _PROMPT.format(size_m=round(size_m), name=asset.name,
                                                    type=asset.type.replace("_", " "), green_pct=green_pct)},
        ]}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    match = re.search(r"\{.*\}", text, re.S)           # the JSON object, even if the model adds a sentence around it
    if not match:
        raise RuntimeError(f"No JSON in the model's answer: {text[:200]}")
    return CanopyInference.model_validate(json.loads(match.group(0)))
