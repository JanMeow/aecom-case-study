from pathlib import Path
from backend.ETL.threshold import BASE_CHANCE

ML_DIR = Path(__file__).parents[1] / "data" / "ml"
TRAINING_DATA = ML_DIR / "storm_outcomes.csv"
MODEL_FILE = ML_DIR / "model.txt"

REFERENCE_YEAR = 2022  # the replay year; age = REFERENCE_YEAR - install_year

FEATURES = ["wind_zone_kt", "asset_type", "condition_rating", "flood_zone",          # also used by the rules
            "tree_canopy_pct", "age_years", "elevation_m", "length_km", "past_storm_failures"]  # ML only
# Fixed category lists, so training and prediction encode text columns the same way
CATEGORIES = {"asset_type": sorted(BASE_CHANCE), "flood_zone": ["AE", "VE", "X"]}

READABLE = {"wind_zone_kt": "wind zone", "asset_type": "asset type", "condition_rating": "condition",
            "flood_zone": "flood zone", "tree_canopy_pct": "tree cover", "age_years": "age",
            "elevation_m": "elevation", "length_km": "line length", "past_storm_failures": "past storm failures"}