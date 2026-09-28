"""Generate SGW's mock source-system exports.

Each source is written in the format the real system would export (its own file type and column
names). IDs are consistent across systems (GIS asset_id) and dates are ISO, so the
aggregator only has to join, not clean. Standard library only; deterministic (seeded).

    python generate.py

Writes:
    sources/gis/assets.geojson                 GIS asset layer (canonical IDs)
    sources/gis/dependencies.csv               GIS network connectivity export
    sources/gis/critical_facilities.geojson    hospitals, shelters, EMS (customer layer)
    sources/maintenance/asset_register.csv     CMMS equipment master (condition, criticality, owner)
    sources/maintenance/work_orders.csv        CMMS work orders 2017–2022, incl. past storm damage
    sources/field_ops/events.jsonl             field app webhooks during Hurricane Ian (timestamped)
    sources/staff/hr_directory.csv             HR export (names, titles, contacts)
    sources/staff/on_call_roster.csv           emergency manager on duty
    ml/storm_outcomes.csv                      synthetic training data for the ML scoring mode

Playbooks (sources/plans/*.md) and weather (sources/weather/, see convert_nhc.py) are not generated here.
"""

import csv
import json
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
ROOT = Path(__file__).parents[1]/"data"
SRC = ROOT / "sources"

# ---------------------------------------------------------------------------
# 1. Assets (GIS is the system of record for IDs and locations)
# ---------------------------------------------------------------------------
# region: North = Hillsborough/Pinellas, Central = Manatee/Sarasota, South = Charlotte/Lee
# columns: id, name, type, lat, lon, elevation_m, coast_km, install_year, customers, region, extra
ASSETS = [
    # Generation
    ("GEN-001", "Hillsborough Bay Energy Center", "generation", 27.792, -82.400, 3.0, 0.3, 1985, 0, "North", {"capacity_mw": 1200}),
    ("GEN-002", "Manatee Energy Center", "generation", 27.604, -82.345, 16.0, 14.0, 2002, 0, "Central", {"capacity_mw": 900}),
    ("GEN-003", "Charlotte Harbor Combined Cycle", "generation", 26.955, -81.935, 6.0, 4.5, 2009, 0, "South", {"capacity_mw": 650}),
    # Substations (bulk 230 kV and distribution 69 kV)
    ("SUB-001", "Tampa Bulk", "substation", 27.990, -82.420, 12.0, 6.0, 1978, 0, "North", {"voltage_kv": 230}),
    ("SUB-002", "Downtown Tampa", "substation", 27.947, -82.458, 4.0, 0.5, 1972, 41000, "North", {"voltage_kv": 69}),
    ("SUB-003", "Westshore", "substation", 27.952, -82.522, 3.0, 0.8, 1988, 36000, "North", {"voltage_kv": 69}),
    ("SUB-004", "Brandon", "substation", 27.940, -82.290, 18.0, 12.0, 1995, 52000, "North", {"voltage_kv": 69}),
    ("SUB-005", "Apollo Beach", "substation", 27.770, -82.400, 2.0, 0.4, 2004, 18000, "North", {"voltage_kv": 69}),
    ("SUB-006", "Pinellas Bulk", "substation", 27.880, -82.720, 6.0, 3.0, 1981, 0, "North", {"voltage_kv": 230}),
    ("SUB-007", "St. Petersburg Downtown", "substation", 27.772, -82.640, 3.0, 0.4, 1969, 39000, "North", {"voltage_kv": 69}),
    ("SUB-008", "Clearwater", "substation", 27.965, -82.790, 8.0, 1.5, 1990, 33000, "North", {"voltage_kv": 69}),
    ("SUB-009", "Manatee Bulk", "substation", 27.580, -82.400, 14.0, 10.0, 1983, 0, "Central", {"voltage_kv": 230}),
    ("SUB-010", "Bradenton", "substation", 27.490, -82.570, 5.0, 1.2, 1986, 34000, "Central", {"voltage_kv": 69}),
    ("SUB-011", "Sarasota", "substation", 27.330, -82.530, 4.0, 0.9, 1979, 38000, "Central", {"voltage_kv": 69}),
    ("SUB-012", "Venice", "substation", 27.100, -82.440, 3.0, 0.7, 1993, 24000, "Central", {"voltage_kv": 69}),
    ("SUB-013", "Port Charlotte", "substation", 26.980, -82.090, 3.0, 1.0, 1987, 31000, "South", {"voltage_kv": 69}),
    ("SUB-014", "Fort Myers South", "substation", 26.580, -81.870, 3.0, 1.8, 1974, 44000, "South", {"voltage_kv": 69}),
    ("SUB-015", "Cape Coral", "substation", 26.600, -81.970, 2.0, 0.6, 1998, 47000, "South", {"voltage_kv": 69}),
    ("SUB-016", "Lee Bulk", "substation", 26.700, -81.750, 9.0, 8.0, 1984, 0, "South", {"voltage_kv": 230}),
    ("SUB-017", "Fort Myers Beach", "substation", 26.460, -81.940, 1.0, 0.1, 1982, 9000, "South", {"voltage_kv": 69}),
    # Water treatment plants
    ("WTP-001", "Tampa Bay Regional WTP", "water_treatment", 27.990, -82.370, 10.0, 7.0, 1980, 180000, "North", {"capacity_mgd": 120}),
    ("WTP-002", "Fort Myers WTP", "water_treatment", 26.620, -81.850, 4.0, 2.5, 1976, 62000, "South", {"capacity_mgd": 24}),
    ("WTP-003", "Pinellas WTP", "water_treatment", 27.950, -82.720, 9.0, 4.0, 1985, 140000, "North", {"capacity_mgd": 80}),
    ("WTP-004", "Manatee WTP", "water_treatment", 27.520, -82.420, 12.0, 9.0, 1992, 95000, "Central", {"capacity_mgd": 54}),
    ("WTP-005", "Cape Coral WTP", "water_treatment", 26.640, -81.990, 3.0, 1.5, 2001, 70000, "South", {"capacity_mgd": 28}),
    ("WTP-006", "Peace River WTP", "water_treatment", 27.030, -81.990, 6.0, 5.0, 1995, 58000, "South", {"capacity_mgd": 36}),
    # Wastewater treatment plants
    ("WWTP-001", "Tampa Bay AWT", "wastewater_treatment", 27.925, -82.430, 2.0, 0.2, 1978, 150000, "North", {"capacity_mgd": 96}),
    ("WWTP-002", "St. Petersburg Southwest WRF", "wastewater_treatment", 27.730, -82.700, 2.0, 0.3, 1983, 90000, "North", {"capacity_mgd": 20}),
    ("WWTP-003", "Fort Myers South WRF", "wastewater_treatment", 26.560, -81.890, 2.0, 0.5, 1980, 60000, "South", {"capacity_mgd": 15}),
    ("WWTP-004", "Sarasota WRF", "wastewater_treatment", 27.350, -82.500, 4.0, 1.5, 1988, 55000, "Central", {"capacity_mgd": 18}),
    ("WWTP-005", "Punta Gorda WRF", "wastewater_treatment", 26.920, -82.030, 2.0, 0.4, 1991, 30000, "South", {"capacity_mgd": 4}),
    # Pumping stations (booster = drinking water, lift = wastewater)
    ("PS-001", "Tampa North Booster", "pumping_station", 28.030, -82.460, 14.0, 7.0, 1990, 38000, "North", {"service": "booster"}),
    ("PS-002", "Davis Islands Lift", "pumping_station", 27.930, -82.455, 1.0, 0.1, 1975, 9000, "North", {"service": "lift"}),
    ("PS-003", "Westshore Lift", "pumping_station", 27.940, -82.530, 2.0, 0.3, 1989, 14000, "North", {"service": "lift"}),
    ("PS-004", "Brandon Booster", "pumping_station", 27.930, -82.300, 17.0, 12.0, 1999, 41000, "North", {"service": "booster"}),
    ("PS-005", "Apollo Beach Lift", "pumping_station", 27.765, -82.410, 1.0, 0.2, 2006, 7000, "North", {"service": "lift"}),
    ("PS-006", "St. Petersburg Booster", "pumping_station", 27.790, -82.660, 6.0, 1.5, 1984, 36000, "North", {"service": "booster"}),
    ("PS-007", "Fort Myers South Booster", "pumping_station", 26.570, -81.860, 3.0, 2.0, 1979, 28000, "South", {"service": "booster"}),
    ("PS-008", "Clearwater Lift", "pumping_station", 27.960, -82.800, 3.0, 0.4, 1992, 12000, "North", {"service": "lift"}),
    ("PS-009", "Bradenton Booster", "pumping_station", 27.490, -82.560, 6.0, 1.5, 1994, 30000, "Central", {"service": "booster"}),
    ("PS-010", "Sarasota Lift", "pumping_station", 27.330, -82.540, 2.0, 0.5, 1981, 15000, "Central", {"service": "lift"}),
    ("PS-011", "Venice Booster", "pumping_station", 27.090, -82.440, 4.0, 1.0, 1997, 21000, "Central", {"service": "booster"}),
    ("PS-012", "Port Charlotte Booster", "pumping_station", 26.990, -82.100, 3.0, 1.2, 1993, 26000, "South", {"service": "booster"}),
    ("PS-013", "Punta Gorda Lift", "pumping_station", 26.930, -82.050, 1.0, 0.2, 1986, 8000, "South", {"service": "lift"}),
    ("PS-014", "Cape Coral Booster", "pumping_station", 26.610, -81.980, 2.0, 1.0, 2003, 33000, "South", {"service": "booster"}),
    ("PS-015", "Cape Coral South Lift", "pumping_station", 26.560, -81.990, 1.0, 0.3, 2000, 11000, "South", {"service": "lift"}),
    ("PS-016", "Fort Myers Beach Lift", "pumping_station", 26.450, -81.950, 1.0, 0.05, 1985, 6000, "South", {"service": "lift"}),
    ("PS-017", "Fort Myers Downtown Lift", "pumping_station", 26.640, -81.870, 2.0, 0.3, 1977, 13000, "South", {"service": "lift"}),
    ("PS-018", "Lehigh Acres Booster", "pumping_station", 26.620, -81.640, 8.0, 18.0, 2021, 22000, "South", {"service": "booster"}),
]

# Transmission lines: id, name, from, to, install_year, region
LINES = [
    ("TL-001", "Bay Energy – Tampa Bulk 230 kV", "GEN-001", "SUB-001", 1985, "North"),
    ("TL-002", "Bay Energy – Pinellas Bulk 230 kV", "GEN-001", "SUB-006", 1986, "North"),
    ("TL-003", "Tampa Bulk – Manatee Bulk 230 kV", "SUB-001", "SUB-009", 1983, "Central"),
    ("TL-004", "Manatee Energy – Manatee Bulk 230 kV", "GEN-002", "SUB-009", 2002, "Central"),
    ("TL-005", "Manatee Bulk – Port Charlotte 230 kV", "SUB-009", "SUB-013", 1987, "Central"),
    ("TL-006", "Port Charlotte – Lee Bulk 230 kV", "SUB-013", "SUB-016", 1988, "South"),
    ("TL-007", "Charlotte Harbor CC – Lee Bulk 230 kV", "GEN-003", "SUB-016", 2009, "South"),
    ("TL-008", "Lee Bulk – Fort Myers South 69 kV", "SUB-016", "SUB-014", 1976, "South"),
    ("TL-009", "Lee Bulk – Cape Coral 69 kV", "SUB-016", "SUB-015", 1998, "South"),
]

# Direct feeds that are not transmission lines (bulk sub -> distribution sub, sub -> water asset, water flows).
# (upstream, downstream, dependency_type)
FEEDS = [
    ("SUB-001", "SUB-002", "power"), ("SUB-001", "SUB-003", "power"), ("SUB-001", "SUB-004", "power"),
    ("SUB-001", "SUB-005", "power"), ("SUB-006", "SUB-007", "power"), ("SUB-006", "SUB-008", "power"),
    ("SUB-009", "SUB-010", "power"), ("SUB-009", "SUB-011", "power"), ("SUB-009", "SUB-012", "power"),
    ("SUB-016", "SUB-017", "power"),
    # power to water assets
    ("SUB-001", "WTP-001", "power"), ("SUB-014", "WTP-002", "power"), ("SUB-006", "WTP-003", "power"),
    ("SUB-009", "WTP-004", "power"), ("SUB-015", "WTP-005", "power"), ("SUB-013", "WTP-006", "power"),
    ("SUB-002", "WWTP-001", "power"), ("SUB-007", "WWTP-002", "power"), ("SUB-014", "WWTP-003", "power"),
    ("SUB-011", "WWTP-004", "power"), ("SUB-013", "WWTP-005", "power"),
    ("SUB-001", "PS-001", "power"), ("SUB-002", "PS-002", "power"), ("SUB-003", "PS-003", "power"),
    ("SUB-004", "PS-004", "power"), ("SUB-005", "PS-005", "power"), ("SUB-007", "PS-006", "power"),
    ("SUB-014", "PS-007", "power"), ("SUB-008", "PS-008", "power"), ("SUB-010", "PS-009", "power"),
    ("SUB-011", "PS-010", "power"), ("SUB-012", "PS-011", "power"), ("SUB-013", "PS-012", "power"),
    ("SUB-013", "PS-013", "power"), ("SUB-015", "PS-014", "power"), ("SUB-015", "PS-015", "power"),
    ("SUB-017", "PS-016", "power"), ("SUB-014", "PS-017", "power"), ("SUB-016", "PS-018", "power"),
    # drinking water: treatment plant -> booster
    ("WTP-001", "PS-001", "water"), ("WTP-001", "PS-004", "water"), ("WTP-003", "PS-006", "water"),
    ("WTP-002", "PS-007", "water"), ("WTP-004", "PS-009", "water"), ("WTP-004", "PS-011", "water"),
    ("WTP-006", "PS-012", "water"), ("WTP-005", "PS-014", "water"), ("WTP-002", "PS-018", "water"),
    # wastewater: a lift station depends on its treatment plant (it backs up if the plant is down)
    ("WWTP-001", "PS-002", "wastewater"), ("WWTP-001", "PS-003", "wastewater"), ("WWTP-001", "PS-005", "wastewater"),
    ("WWTP-002", "PS-008", "wastewater"), ("WWTP-004", "PS-010", "wastewater"), ("WWTP-005", "PS-013", "wastewater"),
    ("WWTP-003", "PS-015", "wastewater"), ("WWTP-003", "PS-016", "wastewater"), ("WWTP-003", "PS-017", "wastewater"),
]

# Standby generators: asset -> hours of fuel on site
BACKUP_POWER = {
    "WTP-001": 72, "WTP-002": 48, "WTP-003": 72, "WTP-004": 48, "WTP-005": 24, "WTP-006": 48,
    "WWTP-001": 48, "WWTP-002": 24, "WWTP-003": 24, "WWTP-004": 24,
    "PS-001": 24, "PS-004": 24, "PS-006": 12, "PS-009": 12, "PS-014": 12,
    # PS-007 (Fort Myers South Booster) has a portable-generator hookup only; see work orders
}

# Critical facilities (fictional names): id, name, kind, lat, lon, power_from, water_from
FACILITIES = [
    ("CF-001", "Bayshore Regional Hospital", "hospital", 27.936, -82.457, "SUB-002", "PS-001"),
    ("CF-002", "Westshore Medical Center", "hospital", 27.955, -82.515, "SUB-003", "PS-001"),
    ("CF-003", "Brandon Community Hospital", "hospital", 27.935, -82.285, "SUB-004", "PS-004"),
    ("CF-004", "Suncoast General Hospital", "hospital", 27.775, -82.650, "SUB-007", "PS-006"),
    ("CF-005", "Manatee Valley Hospital", "hospital", 27.495, -82.565, "SUB-010", "PS-009"),
    ("CF-006", "Sarasota Bay Medical Center", "hospital", 27.335, -82.525, "SUB-011", "PS-009"),
    ("CF-007", "Charlotte Harbor Hospital", "hospital", 26.975, -82.085, "SUB-013", "PS-012"),
    ("CF-008", "Caloosa Regional Medical Center", "hospital", 26.575, -81.865, "SUB-014", "PS-007"),
    ("CF-009", "Cape Coral Community Hospital", "hospital", 26.605, -81.975, "SUB-015", "PS-014"),
    ("CF-010", "Tampa Fairgrounds Shelter", "shelter", 27.990, -82.360, "SUB-004", "PS-004"),
    ("CF-011", "Lee County Civic Center Shelter", "shelter", 26.700, -81.820, "SUB-016", "PS-018"),
    ("CF-012", "South Fort Myers High School Shelter", "shelter", 26.555, -81.860, "SUB-014", "PS-007"),
    ("CF-013", "Pinellas County EOC", "emergency_operations", 27.905, -82.740, "SUB-006", "PS-006"),
    ("CF-014", "Lee County EOC", "emergency_operations", 26.650, -81.800, "SUB-016", "PS-018"),
    ("CF-015", "Gulf Shores Nursing & Rehab", "nursing_home", 26.470, -81.935, "SUB-017", "PS-007"),
    ("CF-016", "Venice Senior Living", "nursing_home", 27.095, -82.435, "SUB-012", "PS-011"),
]

# Condition as the CMMS rates it: 1 = excellent ... 5 = very poor. Unlisted assets are derived from age.
CONDITION_OVERRIDES = {
    "SUB-014": 4, "TL-008": 4, "PS-007": 4, "SUB-017": 4, "PS-016": 4, "SUB-007": 4,
    "WWTP-003": 3, "PS-002": 4, "SUB-002": 3, "PS-018": 1, "GEN-003": 1,
}

# Hidden factor for the ML mode: the rules formula ignores it. Share of the site/corridor under tree canopy.
HIGH_CANOPY = {"TL-003": 55, "TL-005": 62, "TL-006": 48, "TL-008": 58, "SUB-004": 40, "SUB-012": 45, "SUB-016": 35}


def build_assets(rnd: random.Random):
    by_id = {}
    for aid, name, typ, lat, lon, elev, coast, year, cust, region, extra in ASSETS:
        by_id[aid] = dict(asset_id=aid, name=name, asset_type=typ, lat=lat, lon=lon, elevation_m=elev,
                          distance_to_coast_km=coast, install_year=year, customers_served=cust, region=region, **extra)
    for lid, name, a, b, year, region in LINES:
        A, B = by_id[a], by_id[b]
        length = haversine_km(A["lat"], A["lon"], B["lat"], B["lon"])
        by_id[lid] = dict(asset_id=lid, name=name, asset_type="transmission_line",
                          lat=round((A["lat"] + B["lat"]) / 2, 4), lon=round((A["lon"] + B["lon"]) / 2, 4),
                          elevation_m=round((A["elevation_m"] + B["elevation_m"]) / 2, 1),
                          distance_to_coast_km=round(min(A["distance_to_coast_km"], B["distance_to_coast_km"]), 1),
                          install_year=year, customers_served=0, region=region,
                          voltage_kv=230 if "230" in name else 69, length_km=round(length, 1),
                          path=line_path(rnd, A, B))

    for a in by_id.values():
        age = 2022 - a["install_year"]
        cond = CONDITION_OVERRIDES.get(a["asset_id"])
        if cond is None:
            cond = min(5, max(1, round(1 + age / 14 + rnd.uniform(-0.6, 0.6))))
        a["condition_rating"] = cond
        a["has_backup_power"] = a["asset_id"] in BACKUP_POWER
        a["backup_hours"] = BACKUP_POWER.get(a["asset_id"], 0)
        a["flood_zone"] = "VE" if a["distance_to_coast_km"] < 0.2 and a["elevation_m"] <= 2 else (
            "AE" if a["elevation_m"] <= 4 else "X")
        base = HIGH_CANOPY.get(a["asset_id"])
        a["tree_canopy_pct"] = base if base is not None else rnd.randint(5, 30)
        a["critical_facilities"] = [f[0] for f in FACILITIES if a["asset_id"] in (f[5], f[6])]
    return by_id


def build_dependencies():
    rows = []
    for lid, _, a, b, _, _ in LINES:
        rows.append((a, lid, "power"))
        rows.append((lid, b, "power"))
    rows += FEEDS
    return [dict(link_id=f"L{i:03d}", upstream_id=up, downstream_id=down, dependency_type=kind)
            for i, (up, down, kind) in enumerate(rows, 1)]


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def line_path(rnd, A, B, n=4):
    pts = [[A["lon"], A["lat"]]]
    for i in range(1, n):
        t = i / n
        pts.append([round(A["lon"] + (B["lon"] - A["lon"]) * t + rnd.uniform(-0.02, 0.02), 4),
                    round(A["lat"] + (B["lat"] - A["lat"]) * t + rnd.uniform(-0.02, 0.02), 4)])
    pts.append([B["lon"], B["lat"]])
    return pts


# ---------------------------------------------------------------------------
# 2. GIS exports
# ---------------------------------------------------------------------------
GIS_FIELDS = ["asset_id", "name", "asset_type", "region", "elevation_m", "flood_zone",
              "install_year", "customers_served", "has_backup_power", "backup_hours", "tree_canopy_pct",
              "voltage_kv", "capacity_mw", "capacity_mgd", "service", "length_km"]


def write_gis(assets, deps):
    features = []
    for a in assets.values():
        props = {k: a[k] for k in GIS_FIELDS if k in a}
        geom = ({"type": "LineString", "coordinates": a["path"]} if a["asset_type"] == "transmission_line"
                else {"type": "Point", "coordinates": [a["lon"], a["lat"]]})
        features.append({"type": "Feature", "geometry": geom, "properties": props})
    gis = {"type": "FeatureCollection", "name": "sgw_assets",
           "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
           "metadata": {"exported_at": "2022-09-25T06:00:00Z", "system": "SGW Enterprise GIS", "refresh": "daily"},
           "features": features}
    (SRC / "gis" / "assets.geojson").write_text(json.dumps(gis, indent=1))

    write_csv(SRC / "gis" / "dependencies.csv", deps)

    fac = {"type": "FeatureCollection", "name": "critical_facilities", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
         "properties": {"facility_id": fid, "name": name, "kind": kind,
                        "power_from": p, "water_from": w,
                        "beds": {"hospital": 300, "nursing_home": 120}.get(kind),
                        "capacity_people": {"shelter": 1500}.get(kind)}}
        for fid, name, kind, lat, lon, p, w in FACILITIES]}
    (SRC / "gis" / "critical_facilities.geojson").write_text(json.dumps(fac, indent=1))


# ---------------------------------------------------------------------------
# 3. Maintenance (CMMS) exports
# ---------------------------------------------------------------------------
MANUFACTURERS = {
    "substation": ["ABB", "Siemens", "GE Grid"], "transmission_line": ["Southwire", "Prysmian"],
    "generation": ["GE Vernova", "Siemens Energy"], "pumping_station": ["Xylem Flygt", "Grundfos", "KSB"],
    "water_treatment": ["Veolia", "Evoqua"], "wastewater_treatment": ["Veolia", "Evoqua", "Jacobs"],
}

def write_maintenance(rnd, assets):
    reg = []
    for aid, a in assets.items():
        last_insp = date(2022, 1, 1) + timedelta(days=rnd.randint(0, 250))
        reg.append({
            "EQUIP_NO": aid,
            "DESCRIPTION": a["name"].upper(),
            "EQUIP_CLASS": a["asset_type"].replace("_", " ").title(),
            "MANUFACTURER": rnd.choice(MANUFACTURERS[a["asset_type"]]),
            "INSTALL_DATE": date(a["install_year"], rnd.randint(1, 12), rnd.randint(1, 28)).isoformat(),
            "CRITICALITY": "A" if a["customers_served"] > 35000 or a["asset_type"] in ("generation", "transmission_line")
                           or a["critical_facilities"] else ("B" if a["customers_served"] > 15000 else "C"),
            "CONDITION_RATING": a["condition_rating"],
            "LAST_INSPECTION": last_insp.isoformat(),
            "STATUS": "IN SERVICE",
            "OWNER_EMPLOYEE_ID": owner_for(a),
        })
    write_csv(SRC / "maintenance" / "asset_register.csv", reg)

    wos, n = [], 0

    def add(aid, wtype, desc, d, days, cost, failure="", storm="", priority="3"):
        nonlocal n
        n += 1
        done = d + timedelta(days=days)
        wos.append({"WO_NO": f"WO-{18000 + n * 7}", "EQUIP_NO": aid,
                    "WO_TYPE": wtype, "PRIORITY": priority, "DESCRIPTION": desc,
                    "REPORTED": d.isoformat(), "COMPLETED": done.isoformat() if done < date(2022, 9, 25) else "",
                    "STATUS": "CLOSED" if done < date(2022, 9, 25) else "OPEN",
                    "LABOR_HRS": round(rnd.uniform(2, 40) if wtype != "STORM" else rnd.uniform(20, 160), 1),
                    "COST_USD": cost, "FAILURE_CODE": failure, "STORM_EVENT": storm})

    # Routine work: preventive maintenance and inspections
    routine = {
        "substation": ["Transformer oil sampling", "Breaker timing test", "Infrared thermography survey", "Battery bank test"],
        "transmission_line": ["Aerial patrol", "Vegetation clearance", "Insulator wash", "Pole inspection"],
        "generation": ["Turbine borescope inspection", "Black-start test", "Fuel system inspection"],
        "pumping_station": ["Pump vibration analysis", "Wet well cleaning", "Generator load bank test", "Check valve service"],
        "water_treatment": ["Filter media inspection", "Chlorine system service", "Standby generator load test"],
        "wastewater_treatment": ["Clarifier drive service", "Blower overhaul", "Standby generator load test"],
    }
    for aid in assets:
        typ = assets[aid]["asset_type"]
        for _ in range(rnd.randint(2, 4)):
            d = date(2017, 1, 1) + timedelta(days=rnd.randint(0, 2050))
            add(aid, rnd.choice(["PM", "PM", "INSP"]), rnd.choice(routine[typ]), d, rnd.randint(0, 5),
                rnd.randint(400, 9000))

    # Corrective work that explains poor condition
    add("SUB-014", "CM", "Transformer T2 bushing oil leak, temporary repair", date(2022, 3, 14), 3, 18500, "LEAK", priority="2")
    add("SUB-014", "CM", "Control house roof leak over relay panel", date(2021, 11, 2), 12, 7400, "STRUCT")
    add("TL-008", "CM", "Cracked crossarms on 6 structures, replacement deferred to FY23", date(2022, 5, 20), 0, 0, "STRUCT", priority="2")
    add("TL-008", "INSP", "Vegetation encroachment within 3 ft of conductor, spans 14–19", date(2022, 7, 8), 1, 900, "VEG")
    add("PS-007", "CM", "Standby generator failed load test; unit removed, portable hookup only", date(2022, 6, 1), 0, 0, "GEN", priority="1")
    add("PS-016", "CM", "Wet well level sensor corroded (salt air)", date(2022, 4, 11), 2, 2600, "CORR")
    add("SUB-017", "CM", "Switchgear enclosure corrosion, below design flood elevation", date(2021, 9, 30), 5, 11200, "CORR")
    add("PS-002", "CM", "Pump 2 impeller wear, running on single pump", date(2022, 8, 22), 30, 0, "MECH", priority="2")

    # Past storm damage (history for the AI and labels for "has this happened before?")
    storms = [
        ("Hurricane Irma 2017", date(2017, 9, 11), ["SUB-014", "TL-008", "SUB-017", "PS-016", "SUB-015", "PS-007",
                                                     "SUB-012", "TL-006", "PS-013", "SUB-004"]),
        ("Tropical Storm Eta 2020", date(2020, 11, 12), ["PS-002", "PS-005", "SUB-005", "PS-008", "SUB-003"]),
        ("Hurricane Elsa 2021", date(2021, 7, 7), ["SUB-007", "PS-010", "SUB-011", "TL-005"]),
    ]
    damage = {"substation": ("Flooded control cabinet / relay failure", "FLOOD"),
              "transmission_line": ("Downed conductor, tree contact", "VEG"),
              "pumping_station": ("Lost utility power, pump down; generator dispatched", "POWER"),
              "water_treatment": ("Intake screen debris", "DEBRIS"), "wastewater_treatment": ("Influent surge overflow", "FLOOD")}
    for storm, d, hit in storms:
        for aid in hit:
            desc, code = damage[assets[aid]["asset_type"]]
            add(aid, "STORM", f"{storm}: {desc}", d + timedelta(days=rnd.randint(0, 2)), rnd.randint(1, 9),
                rnd.randint(15000, 240000), code, storm, priority="1")

    rnd.shuffle(wos)
    write_csv(SRC / "maintenance" / "work_orders.csv", wos)
    return reg, wos


# ---------------------------------------------------------------------------
# 4. Staff directory (HR) — not linked to assets
# ---------------------------------------------------------------------------
STAFF = [
    # id, first, last, title, department, team, location
    ("E1001", "Maria", "Delgado", "Emergency Manager", "Emergency Management", "Emergency Management", "Tampa HQ"),
    ("E1002", "Kwame", "Asante", "Emergency Manager", "Emergency Management", "Emergency Management", "Fort Myers"),
    ("E1003", "Priya", "Raman", "VP Operations", "Operations", "Executive", "Tampa HQ"),
    ("E1004", "Tom", "Becker", "T&D Operations Supervisor", "Transmission & Distribution", "T&D Ops North", "Tampa HQ"),
    ("E1005", "Aisha", "Khan", "Distribution Engineer", "Transmission & Distribution", "T&D Ops North", "Tampa HQ"),
    ("E1006", "Luis", "Ortega", "T&D Operations Supervisor", "Transmission & Distribution", "T&D Ops Central", "Bradenton"),
    ("E1007", "Hannah", "Cole", "T&D Operations Supervisor", "Transmission & Distribution", "T&D Ops South", "Fort Myers"),
    ("E1008", "Daniel", "Nguyen", "Substation Technician", "Transmission & Distribution", "T&D Ops South", "Fort Myers"),
    ("E1009", "Grace", "Okafor", "Transmission Lead", "Transmission & Distribution", "Transmission", "Tampa HQ"),
    ("E1010", "Robert", "Hale", "Plant Manager", "Generation", "Generation", "Apollo Beach"),
    ("E1011", "Sofia", "Marquez", "Water Operations Supervisor", "Water Services", "Water Ops North", "Tampa HQ"),
    ("E1012", "James", "Whitfield", "Water Operations Supervisor", "Water Services", "Water Ops Central", "Bradenton"),
    ("E1013", "Mei", "Chen", "Water Operations Supervisor", "Water Services", "Water Ops South", "Fort Myers"),
    ("E1014", "Carlos", "Rivera", "Treatment Plant Operator", "Water Services", "Water Ops South", "Fort Myers"),
    ("E1015", "Olivia", "Brooks", "Wastewater Manager", "Water Services", "Wastewater Ops", "Tampa HQ"),
    ("E1016", "Samuel", "Adeyemi", "Field Crew Supervisor", "Field Operations", "Field Crews South", "Fort Myers"),
    ("E1017", "Emily", "Park", "Field Crew Supervisor", "Field Operations", "Field Crews North", "Tampa HQ"),
    ("E1018", "Nadia", "Haddad", "Communications Manager", "Corporate Communications", "Communications", "Tampa HQ"),
    ("E1019", "Brian", "Walsh", "Regulatory Affairs Manager", "Regulatory", "Regulatory", "Tampa HQ"),
]
MANAGERS = {"E1004": "E1003", "E1006": "E1003", "E1007": "E1003", "E1009": "E1003", "E1010": "E1003",
            "E1011": "E1003", "E1012": "E1003", "E1013": "E1003", "E1015": "E1003", "E1001": "E1003",
            "E1002": "E1001", "E1005": "E1004", "E1008": "E1007", "E1014": "E1013", "E1016": "E1007",
            "E1017": "E1004", "E1018": "E1003", "E1019": "E1003"}

# Responsible person per asset, as recorded in the CMMS register (OWNER_EMPLOYEE_ID)
SUBSTATION_OWNER = {"North": "E1004", "Central": "E1006", "South": "E1007"}
WATER_OWNER = {"North": "E1011", "Central": "E1012", "South": "E1013"}


def owner_for(a):
    typ, service = a["asset_type"], a.get("service")
    if typ == "substation":
        return SUBSTATION_OWNER[a["region"]]
    if typ == "transmission_line":
        return "E1009"
    if typ == "generation":
        return "E1010"
    if typ == "water_treatment" or service == "booster":
        return WATER_OWNER[a["region"]]
    return "E1015"  # wastewater plants and lift stations


def write_staff():
    rows = []
    for eid, first, last, title, dept, team, loc in STAFF:
        rows.append({"EMPLOYEE_ID": eid, "FIRST_NAME": first, "LAST_NAME": last, "JOB_TITLE": title,
                     "DEPARTMENT": dept, "TEAM": team, "WORK_LOCATION": loc,
                     "EMAIL": f"{first[0].lower()}{last.lower()}@sgw.example",
                     "WORK_PHONE": f"+1-813-555-{int(eid[1:]) - 900:04d}",
                     "MANAGER_ID": MANAGERS.get(eid, ""), "EMPLOYMENT_STATUS": "Active"})
    write_csv(SRC / "staff" / "hr_directory.csv", rows)
    write_csv(SRC / "staff" / "on_call_roster.csv", [
        {"role": "Emergency Manager on duty", "employee_id": "E1001", "start": "2022-09-19T12:00:00Z", "end": "2022-09-28T12:00:00Z"},
        {"role": "Emergency Manager on duty", "employee_id": "E1002", "start": "2022-09-28T12:00:00Z", "end": "2022-10-05T12:00:00Z"},
        {"role": "Executive on call", "employee_id": "E1003", "start": "2022-09-19T12:00:00Z", "end": "2022-10-05T12:00:00Z"},
    ])


# ---------------------------------------------------------------------------
# 5. Field operations webhooks during Hurricane Ian (UTC; replay emits them by received_at)
# ---------------------------------------------------------------------------
FIELD_EVENTS = [
    # time (UTC), type, asset, crew, status, notes
    ("2022-09-26T14:10:00Z", "crew.prestaged", None, "CRW-S1", "staged", "Crew S1 staged at Fort Myers service center"),
    ("2022-09-26T16:40:00Z", "asset.prep_completed", "WTP-001", "CRW-N2", "done", "Generator fuel topped up to 72 h"),
    ("2022-09-26T19:05:00Z", "asset.prep_completed", "SUB-005", "CRW-N1", "done", "Sandbags placed around control house"),
    ("2022-09-27T01:30:00Z", "asset.prep_completed", "PS-002", "CRW-N2", "partial", "Only one pump available; portable pump requested"),
    ("2022-09-27T13:15:00Z", "crew.prestaged", None, "CRW-MA1", "staged", "Mutual aid crew (40 linemen) arrived Lakeland"),
    ("2022-09-27T15:50:00Z", "asset.prep_completed", "PS-007", "CRW-S2", "blocked", "Portable generator not yet delivered to PS-007"),
    ("2022-09-27T18:20:00Z", "asset.prep_completed", "SUB-017", "CRW-S1", "done", "Flood barriers installed; access road expected to flood"),
    ("2022-09-27T22:45:00Z", "asset.prep_completed", "WWTP-003", "CRW-S2", "done", "Influent pumps tested; bypass pump staged"),
    ("2022-09-28T02:10:00Z", "asset.prep_completed", "PS-007", "CRW-S2", "done", "Portable 250 kW generator connected at PS-007"),
    ("2022-09-28T09:30:00Z", "crew.sheltering", None, "CRW-S1", "sheltering", "South crews sheltering in place, winds above 45 mph"),
    ("2022-09-28T17:05:00Z", "asset.outage_reported", "SUB-017", None, "out", "SCADA lost; Fort Myers Beach feeders de-energised"),
    ("2022-09-28T17:40:00Z", "asset.outage_reported", "PS-016", None, "out", "Lift station offline, surge water in wet well"),
    ("2022-09-28T18:20:00Z", "asset.outage_reported", "TL-008", None, "out", "Line tripped and locked out, suspected structure failure"),
    ("2022-09-28T18:25:00Z", "asset.outage_reported", "SUB-014", None, "out", "De-energised after TL-008 lockout; Caloosa Regional on hospital backup"),
    ("2022-09-28T19:10:00Z", "asset.outage_reported", "SUB-015", None, "out", "Cape Coral substation offline"),
    ("2022-09-28T19:30:00Z", "asset.outage_reported", "PS-015", None, "out", "Lost utility power"),
    ("2022-09-28T20:05:00Z", "asset.outage_reported", "PS-013", None, "out", "Punta Gorda lift station flooded"),
    ("2022-09-28T20:40:00Z", "asset.status_update", "PS-007", None, "on_generator", "Running on portable generator"),
    ("2022-09-28T21:15:00Z", "asset.outage_reported", "SUB-013", None, "out", "Port Charlotte substation lost its 230 kV supply (TL-005)"),
    ("2022-09-28T22:00:00Z", "asset.status_update", "WTP-005", None, "on_generator", "Running on standby generator, 24 h fuel"),
    ("2022-09-29T00:30:00Z", "asset.status_update", "SUB-012", None, "degraded", "Venice feeders 3 and 7 out, tree contact"),
    ("2022-09-29T11:00:00Z", "damage.assessed", "SUB-017", "CRW-S1", "major_damage", "Control house flooded to 1.2 m, switchgear destroyed"),
    ("2022-09-29T12:30:00Z", "damage.assessed", "TL-008", "CRW-S3", "major_damage", "4 structures down, spans 14–19 (same spans flagged in July)"),
    ("2022-09-29T13:10:00Z", "damage.assessed", "PS-016", "CRW-S2", "major_damage", "Pumps and control panel submerged"),
    ("2022-09-29T14:45:00Z", "asset.status_update", "WTP-005", None, "fuel_low", "Generator fuel at 6 h; delivery requested"),
    ("2022-09-29T16:00:00Z", "asset.restored", "SUB-015", "CRW-MA1", "restored", "Cape Coral substation re-energised (partial load)"),
    ("2022-09-29T18:20:00Z", "asset.restored", "SUB-013", "CRW-MA1", "restored", "Port Charlotte re-energised after TL-005 patrol and switching"),
    ("2022-09-29T20:10:00Z", "asset.restored", "PS-015", "CRW-S2", "restored", "Utility power back"),
    ("2022-09-30T09:00:00Z", "asset.restored", "SUB-012", "CRW-N1", "restored", "Venice feeders restored"),
]


def write_field_ops():
    lines = []
    for i, (ts, etype, aid, crew, status, notes) in enumerate(FIELD_EVENTS, 1):
        lines.append({"event_id": f"fo-{i:04d}", "event_type": etype, "source": "SGW FieldOps mobile app",
                      "received_at": ts, "asset_id": aid, "crew_id": crew, "status": status, "notes": notes})
    with open(SRC / "field_ops" / "events.jsonl", "w") as f:
        for ev in lines:
            f.write(json.dumps(ev) + "\n")
    return lines


# ---------------------------------------------------------------------------
# 6. Synthetic storm outcomes for the ML scoring mode (clearly synthetic)
# ---------------------------------------------------------------------------
# Features are only fields the live system has: the wind zone (from the advisory) and AggregatedData fields.
# The hidden "true" failure chance starts from the same table as the rules score, then adds effects the rules
# ignore, so an ML model trained on it can beat the rules and its explanations show why.
TRUE_BASE = {"transmission_line": {34: 0.10, 50: 0.30, 64: 0.65}, "substation": {34: 0.05, 50: 0.20, 64: 0.50},
             "pumping_station": {34: 0.03, 50: 0.10, 64: 0.35}, "wastewater_treatment": {34: 0.02, 50: 0.08, 64: 0.30},
             "water_treatment": {34: 0.01, 50: 0.05, 64: 0.25}, "generation": {34: 0.01, 50: 0.05, 64: 0.20}}
TRUE_CONDITION = {1: 0.8, 2: 0.9, 3: 1.0, 4: 1.3, 5: 1.6}


def true_chance(a, zone_kt, past_failures):
    """Synthetic ground truth. Rules use: type, zone, condition, flood zone. Hidden extras marked (ML)."""
    if zone_kt == 0:
        return 0.005
    p = TRUE_BASE[a["asset_type"]][zone_kt] * TRUE_CONDITION[a["condition_rating"]]
    if a["asset_type"] in ("transmission_line", "substation"):
        p *= 1 + 1.5 * a["tree_canopy_pct"] / 100             # (ML) trees fall on lines and into substations
    p *= 1 + max(0, 2022 - a["install_year"] - 30) / 60       # (ML) equipment over 30 years old is weaker
    p *= 1 + a.get("length_km", 0) / 300                      # (ML) longer lines have more to break
    p += 0.10 * past_failures                                 # (ML) failed in a past storm, likely again
    if zone_kt == 64 and a["flood_zone"] in ("AE", "VE"):     # surge: the rules add a flat 30%,
        p += {1: 0.45, 2: 0.35, 3: 0.20}.get(round(a["elevation_m"]), 0.10)   # (ML) truth depends on elevation
    return min(0.95, p)  # nothing is certain


def write_ml(rnd, assets, wos):
    past = {}
    for w in wos:
        if w["WO_TYPE"] == "STORM":
            past[w["EQUIP_NO"]] = past.get(w["EQUIP_NO"], 0) + 1
    rows = []
    for s in range(400):
        # a random storm: centre somewhere over the service area, random size (radius of the 64 kt zone)
        c_lat, c_lon = rnd.uniform(26.2, 28.4), rnd.uniform(-82.9, -81.6)
        r64 = rnd.uniform(15, 50)
        for a in assets.values():
            d = haversine_km(a["lat"], a["lon"], c_lat, c_lon)
            zone = 64 if d <= r64 else 50 if d <= r64 * 1.8 else 34 if d <= r64 * 3.5 else 0
            p = true_chance(a, zone, past.get(a["asset_id"], 0))
            rows.append({"scenario_id": f"S{s:03d}", "asset_id": a["asset_id"], "asset_type": a["asset_type"],
                         "wind_zone_kt": zone, "condition_rating": a["condition_rating"], "flood_zone": a["flood_zone"],
                         "elevation_m": a["elevation_m"], "age_years": 2022 - a["install_year"],
                         "tree_canopy_pct": a["tree_canopy_pct"], "length_km": a.get("length_km", 0),
                         "past_storm_failures": past.get(a["asset_id"], 0), "failed": int(rnd.random() < p)})
    write_csv(ROOT / "ml" / "storm_outcomes.csv", rows)
    return rows


# ---------------------------------------------------------------------------
def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    rnd = random.Random(SEED)
    assets = build_assets(rnd)
    deps = build_dependencies()
    write_gis(assets, deps)
    reg, wos = write_maintenance(rnd, assets)
    write_staff()
    events = write_field_ops()
    ml = write_ml(rnd, assets, wos)

    print(f"assets {len(assets)}, dependencies {len(deps)}, facilities {len(FACILITIES)}, register {len(reg)}, "
          f"work orders {len(wos)}, field events {len(events)}, staff {len(STAFF)}, ml rows {len(ml)} "
          f"({sum(r['failed'] for r in ml) / len(ml):.0%} failed)")


if __name__ == "__main__":
    main()
