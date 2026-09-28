"""
ML scoring mode (Phase 2 preview): predict each asset's OWN chance of failing with LightGBM.

It replaces only step 2 of the rules score (own_chance). Likelihood (upstream) and consequence (downstream)
stay the same, so the two modes can be compared like for like.

    train()    learn from data/ml/storm_outcomes.csv (synthetic past storms), check on held-out storms,
               compare with the rules, save the model to data/ml/model.txt
    predict()  own chance per asset from AggregatedData + wind zone, with the top reasons (SHAP values)

Features are only fields the live system has; see data/README.md "Synthetic ML labels".
"""
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from backend.ETL.model import AggregatedData
from backend.ETL.threshold import BASE_CHANCE, CONDITION_MULTIPLIER, FLOOD_BONUS, FLOOD_ZONES
from .settings import ( FEATURES, CATEGORIES, TRAINING_DATA, MODEL_FILE, REFERENCE_YEAR, READABLE)


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    X = df[FEATURES].copy()
    for col, cats in CATEGORIES.items():
        X[col] = pd.Categorical(X[col], categories=cats)
    return X


def _rules_chance(row) -> float:
    """The rules' own chance for one training row (same formula as risk_score._chance), as a baseline."""
    if row.wind_zone_kt == 0:
        return 0.0
    p = BASE_CHANCE[row.asset_type][row.wind_zone_kt] * CONDITION_MULTIPLIER[row.condition_rating]
    if row.wind_zone_kt == 64 and row.flood_zone in FLOOD_ZONES:
        p += FLOOD_BONUS
    return min(1.0, p)


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------
def train(path: Path = TRAINING_DATA, test_share: float = 0.2, save: bool = True) -> tuple[lgb.Booster, dict]:
    """Train on past storms, test on storms the model has never seen, compare with the rules.

    Splits by storm (scenario_id), not by row, so the test is "a new storm", not "a new row from a known storm".
    Metrics are on assets inside a wind zone, where ranking matters:
        AUC    how well it ranks assets that failed above ones that didn't (1.0 perfect, 0.5 random)
        Brier  mean squared error of the predicted chance (lower is better)

    Returns (model, metrics). Saves the model to MODEL_FILE.
    """
    df = pd.read_csv(path)
    storms = sorted(df.scenario_id.unique())
    test_storms = set(storms[int(len(storms) * (1 - test_share)):])
    test = df.scenario_id.isin(test_storms)

    # small trees and at least 200 rows per leaf: each asset appears in few storms, so this stops the model
    # memorising individual assets and keeps its chances realistic (no false "100% certain")
    clf = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=8, min_child_samples=200, verbose=-1)
    clf.fit(_prepare(df[~test]), df.failed[~test])
    model = clf.booster_

    held_out = df[test & (df.wind_zone_kt > 0)].copy()
    held_out["ml"] = model.predict(_prepare(held_out))
    held_out["rules"] = held_out.apply(_rules_chance, axis=1)
    metrics = {"train_storms": len(storms) - len(test_storms), "test_storms": len(test_storms)}
    for name in ("rules", "ml"):
        metrics[f"{name}_auc"] = round(roc_auc_score(held_out.failed, held_out[name]), 3)
        metrics[f"{name}_brier"] = round(brier_score_loss(held_out.failed, held_out[name]), 4)

    importance = _mean_abs_contributions(model, _prepare(held_out))
    metrics["feature_importance"] = {k: round(float(v), 3) for k, v in importance.items()}

    if save:
        model.save_model(str(MODEL_FILE))
    return model, metrics


def _mean_abs_contributions(model: lgb.Booster, X: pd.DataFrame) -> dict[str, float]:
    """Share of the model's decisions each feature accounts for, on average (from SHAP values)."""
    contrib = np.abs(model.predict(X, pred_contrib=True)[:, :-1]).mean(axis=0)
    share = contrib / contrib.sum()
    return dict(sorted(zip(FEATURES, share), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------
def load_model(path: Path = MODEL_FILE) -> lgb.Booster:
    return lgb.Booster(model_file=str(path))


def features_for(asset: AggregatedData, zone_kt: int) -> dict:
    """One feature row from the aggregated record and the wind zone the asset is in."""
    return {
        "wind_zone_kt": zone_kt,
        "asset_type": asset.type,
        "condition_rating": asset.condition_rating or 3,
        "flood_zone": asset.flood_zone,
        "tree_canopy_pct": asset.tree_canopy_pct or 0,
        "age_years": REFERENCE_YEAR - asset.install_year,
        "elevation_m": asset.elevation_m,
        "length_km": asset.attributes.get("length_km", 0),
        "past_storm_failures": sum(1 for h in asset.history if h.type == "STORM"),
    }


def _fmt(value) -> str:
    """12.0 -> '12', 'transmission_line' -> 'transmission line'."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace("_", " ")


def predict(model: lgb.Booster, assets: dict[str, AggregatedData], zones: dict[str, int],
            top_n: int = 3) -> dict[str, tuple[float, list[str]]]:
    """Own chance of failing per asset, with the features that pushed it up or down the most.

    zones: asset_id -> wind zone (0/34/50/64), e.g. from risk_score.wind_zones().
    Returns asset_id -> (chance, reasons), e.g. (0.91, ["tree cover 58 raises it", "past storm failures 1 raises it"]).
    Reasons come from SHAP values (LightGBM pred_contrib): how much each feature moved this prediction.
    """
    ids = list(assets)
    X = _prepare(pd.DataFrame([features_for(assets[a], zones[a]) for a in ids]))
    chances = model.predict(X)
    contrib = model.predict(X, pred_contrib=True)[:, :-1]  # last column is the baseline

    results = {}
    for i, asset_id in enumerate(ids):
        order = np.argsort(-np.abs(contrib[i]))[:top_n]
        reasons = [f"{READABLE[FEATURES[j]]} {_fmt(X.iloc[i][FEATURES[j]])} {'raises' if contrib[i][j] > 0 else 'lowers'} it"
                   for j in order if abs(contrib[i][j]) > 0.05]
        results[asset_id] = (round(float(chances[i]), 3), reasons)
    return results



@lru_cache
def get_model() -> lgb.Booster:
    """The trained model, loaded on first use (so importing this module doesn't need model.txt yet)."""
    return load_model()


if __name__ == "__main__":
    from backend.ETL.extraction import load_advisory, load_processed_assets
    from backend.ETL.risk_score import wind_zones

    model, metrics = train()
    print(f"Trained on {metrics['train_storms']} storms, tested on {metrics['test_storms']} unseen storms")
    print(f"  rules  AUC {metrics['rules_auc']}  Brier {metrics['rules_brier']}")
    print(f"  ML     AUC {metrics['ml_auc']}  Brier {metrics['ml_brier']}")
    print("  feature importance:", metrics["feature_importance"])

    assets, advisory = load_processed_assets(), load_advisory(25)
    zones = {a: wind_zones(asset, advisory)[0] for a, asset in assets.items()} 
    preds = predict(load_model(), assets, zones)
    print("\nAdvisory 25, own chance (ML), top 8:")
    for asset_id, (chance, reasons) in sorted(preds.items(), key=lambda kv: -kv[1][0])[:8]:
        print(f"  {asset_id:9} {chance:.2f}  {'; '.join(reasons)}")
