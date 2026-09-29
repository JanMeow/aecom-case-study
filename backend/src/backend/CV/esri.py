import math

import httpx

ESRI_EXPORT = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"
ESRI_ATTRIBUTION = "Esri, Maxar, Earthstar Geographics, and the GIS User Community"
_METRES_PER_DEG_LAT = 111_320


async def get_satellite_image(lat: float, lon: float, size_m: float = 300, px: int = 512) -> bytes:
    """Satellite image (PNG bytes) of a square area centred on a point, from Esri World Imagery.

    size_m: width of the area in metres (300 m shows a substation and its surroundings).
    px: image width/height in pixels.
    """
    # a square box size_m wide around the point; a degree of longitude shrinks with latitude
    half_lat = (size_m / 2) / _METRES_PER_DEG_LAT
    half_lon = (size_m / 2) / (_METRES_PER_DEG_LAT * math.cos(math.radians(lat)))
    bbox = f"{lon - half_lon},{lat - half_lat},{lon + half_lon},{lat + half_lat}"

    params = {"bbox": bbox, "bboxSR": 4326, "imageSR": 3857, "size": f"{px},{px}",
              "format": "png", "f": "image"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(ESRI_EXPORT, params=params)
    response.raise_for_status()
    # Esri reports some errors as JSON with status 200, so check we really got an image
    if not response.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(f"Esri returned no image: {response.text[:200]}")
    return response.content
