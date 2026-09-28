"""Convert raw NHC Hurricane Ian (AL092022) advisory shapefiles into GeoJSON for the replay connector.

Input:  sources/weather/ian_2022/raw/al092022_{5day,fcst}_NNN.zip  (downloaded from the NHC GIS archive)
Output: sources/weather/ian_2022/advisories.geojson               (all advisories in one FeatureCollection:
                                                                    properties.advisories = list in replay order,
                                                                    each feature tagged with its advisory number)

Run once (outputs are committed):  uv run --with pyshp python convert_nhc.py
Source: https://www.nhc.noaa.gov/gis/archive_forecast_results.php?id=al09&year=2022
"""

import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import shapefile  # pyshp

ROOT = Path(__file__).parents[1] /"data" /"sources" / "weather" / "ian_2022"
RAW = ROOT / "raw"
OUT = ROOT / "advisories.geojson"

# NHC writes the advisory time as local text, e.g. "1100 PM EDT Tue Sep 27 2022"
TZ_OFFSETS = {"EDT": -4, "EST": -5, "CDT": -5, "CST": -6, "AST": -4}

WATCH_WARNING = {
    "HWR": "Hurricane Warning",
    "HWA": "Hurricane Watch",
    "TWR": "Tropical Storm Warning",
    "TWA": "Tropical Storm Watch",
}


def read_layer(zf: zipfile.ZipFile, suffix: str) -> shapefile.Reader | None:
    stems = {n.rsplit(".", 1)[0] for n in zf.namelist() if n.endswith(".shp")}
    stem = next((s for s in stems if s.endswith(suffix)), None)
    if stem is None:
        return None
    return shapefile.Reader(
        shp=io.BytesIO(zf.read(stem + ".shp")),
        shx=io.BytesIO(zf.read(stem + ".shx")),
        dbf=io.BytesIO(zf.read(stem + ".dbf")),
    )


def round_coords(obj, nd=4):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(v, nd) for v in obj]
        return [round_coords(o, nd) for o in obj]
    return obj


def geometry(shape) -> dict:
    geo = shape.__geo_interface__
    return {"type": geo["type"], "coordinates": round_coords(geo["coordinates"])}


def parse_adv_time(text: str) -> str:
    m = re.match(r"(\d{3,4}) (AM|PM) (\w{3}) \w{3} (\w{3}) (\d{1,2}) (\d{4})", text.strip())
    hhmm, ampm, tz, mon, day, year = m.groups()
    hhmm = hhmm.zfill(4)
    hour, minute = int(hhmm[:2]) % 12, int(hhmm[2:])
    if ampm == "PM":
        hour += 12
    local = datetime.strptime(f"{year} {mon} {day}", "%Y %b %d").replace(hour=hour, minute=minute)
    utc = local - timedelta(hours=TZ_OFFSETS[tz])
    return utc.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def synoptic_to_iso(code: str) -> str:
    return datetime.strptime(code, "%Y%m%d%H").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def convert(num: str) -> tuple[dict, list[dict]]:
    features = []
    five = zipfile.ZipFile(RAW / f"al092022_5day_{num}.zip")
    fcst = zipfile.ZipFile(RAW / f"al092022_fcst_{num}.zip")

    cone = read_layer(five, "_5day_pgn")
    for sr in cone.shapeRecords():
        features.append({"type": "Feature", "geometry": geometry(sr.shape),
                         "properties": {"layer": "cone", "forecast_hours": 120}})

    track = read_layer(five, "_5day_lin")
    for sr in track.shapeRecords():
        features.append({"type": "Feature", "geometry": geometry(sr.shape),
                         "properties": {"layer": "track"}})

    pts = read_layer(five, "_5day_pts")
    points = []
    for sr in pts.shapeRecords():
        r = sr.record.as_dict()
        lon, lat = sr.shape.points[0]
        props = {
            "layer": "forecast_point",
            "tau_hours": int(r["TAU"]),
            "valid_label": r["FLDATELBL"],
            "max_wind_kt": int(r["MAXWIND"]),
            "gust_kt": int(r["GUST"]),
            "saffir_simpson": int(r["SSNUM"]),
            "storm_type": r["TCDVLP"],
        }
        points.append((props, lat, lon, r))
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 4), round(lat, 4)]},
                         "properties": props})

    ww = read_layer(five, "_ww_wwlin")
    if ww is not None:
        for sr in ww.shapeRecords():
            code = sr.record.as_dict()["TCWW"]
            features.append({"type": "Feature", "geometry": geometry(sr.shape),
                             "properties": {"layer": "watch_warning", "code": code,
                                            "label": WATCH_WARNING.get(code, code)}})

    synoptic = None
    for suffix, kind in (("_initialradii", "current"), ("_forecastradii", "forecast")):
        radii = read_layer(fcst, suffix)
        if radii is None:
            continue
        for sr in radii.shapeRecords():
            r = sr.record.as_dict()
            synoptic = r["SYNOPTIME"]
            if kind == "forecast" and int(r["TAU"]) == 0:
                continue  # identical to the initial radii
            features.append({"type": "Feature", "geometry": geometry(sr.shape),
                             "properties": {"layer": "wind_radii", "kind": kind, "threshold_kt": int(r["RADII"]),
                                            "tau_hours": int(r["TAU"]), "valid_time": synoptic_to_iso(r["VALIDTIME"])}})

    now_props, lat, lon, rec = min(points, key=lambda p: p[0]["tau_hours"])
    meta = {
        "advisory": int(num),
        "issued_at": parse_adv_time(rec["ADVDATE"]),
        "issued_label": rec["ADVDATE"],
        "synoptic_time": synoptic_to_iso(synoptic) if synoptic else None,
        "center": {"lat": round(lat, 2), "lon": round(lon, 2)},
        "max_wind_kt": now_props["max_wind_kt"],
        "saffir_simpson": now_props["saffir_simpson"],
        "storm_type": now_props["storm_type"],
    }
    for f in features:
        f["properties"] = {"advisory": int(num), **f["properties"]}
    return meta, features


def _dumps(obj) -> str:
    """indent=2, but each [lon, lat] pair stays on one line so the file stays readable and small."""
    text = json.dumps(obj, indent=2)
    return re.sub(r"\[\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\]", r"[\1, \2]", text)


def main():
    nums = sorted({re.search(r"_(\d{3})\.zip$", p.name).group(1) for p in RAW.glob("al092022_5day_*.zip")})
    converted = sorted((convert(n) for n in nums), key=lambda mf: mf[0]["issued_at"])
    index = [meta for meta, _ in converted]
    OUT.write_text(_dumps({
        "type": "FeatureCollection",
        "properties": {
            "storm": "Hurricane Ian", "storm_id": "AL092022",
            "source": "NHC GIS archive, https://www.nhc.noaa.gov/gis/archive_forecast_results.php?id=al09&year=2022",
            "advisories": index,
        },
        "features": [f for _, features in converted for f in features],
    }))
    for m in index:
        print(f"adv {m['advisory']:>3}  {m['issued_at']}  {m['center']}  {m['max_wind_kt']} kt  cat {m['saffir_simpson']}")


if __name__ == "__main__":
    main()
