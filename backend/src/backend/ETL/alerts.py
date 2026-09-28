"""
Alert rules: deterministic, no AI. Replays every advisory up to the one asked for, so the result is the same
whether the replay moves forwards or backwards.

    High      -> notify the asset's owner
    Critical  -> open the incident room (first time) or add the asset and its people to it

Each asset alerts once per tier, and again only if its tier rises (High -> Critical). No repeat alerts.
Room members: owners of every Critical asset, owners of the assets downstream of them,
and the Emergency Manager on duty at the time.
"""
from functools import lru_cache

from backend.ETL.extraction import load_advisory, load_advisory_index, load_processed_assets, on_call
from backend.ETL.model import AggregatedData, Alert, IncidentRoom, Owner, RiskResult
from backend.ETL.risk_score import ml_risk_score, standard_risk_score

ALERT_TIERS = {"High": 1, "Critical": 2}   # tiers that trigger an action, ranked


@lru_cache
def scores_for(advisory: int, mode: str) -> dict[str, RiskResult]:
    """Scores for one advisory and mode, computed once then cached (used by /risks and the alert rules)."""
    assets, adv = load_processed_assets(), load_advisory(advisory)
    return (ml_risk_score if mode == "ml" else standard_risk_score)(assets, adv)


def _add(people: list[Owner], person: Owner | None) -> None:
    if person and all(p.employee_id != person.employee_id for p in people):
        people.append(person)


def alerts_until(advisory: int, mode: str = "standard") -> tuple[list[Alert], IncidentRoom | None]:
    """All alerts fired from the first advisory up to and including this one, and the incident room if open."""
    assets: dict[str, AggregatedData] = load_processed_assets()
    alerted: dict[str, int] = {}                  # asset_id -> highest tier already alerted
    alerts: list[Alert] = []
    room: IncidentRoom | None = None

    for meta in load_advisory_index():
        n = meta["advisory"]
        if n > advisory:
            break
        scores = scores_for(n, mode)
        issued_at = load_advisory(n).issued_at
        for r in sorted(scores.values(), key=lambda r: -r.score):
            rank = ALERT_TIERS.get(r.tier, 0)
            if rank <= alerted.get(r.asset_id, 0):
                continue                          # nothing new for this asset
            alerted[r.asset_id] = rank
            asset = assets[r.asset_id]

            if r.tier == "High":
                alerts.append(Alert(
                    advisory=n, issued_at=issued_at, asset_id=r.asset_id, asset_name=asset.name, tier="High",
                    action="notify_owner", recipients=[asset.owner] if asset.owner else [],
                    message=f"{asset.name} ({r.asset_id}) is at High risk ({r.score:.2f}). Please review preparations.",
                    reasons=r.reasons))
                continue

            # Critical: open the room, or add this asset and its people to it
            people: list[Owner] = []
            _add(people, asset.owner)
            for d in asset.downstream:
                _add(people, assets[d].owner)
            _add(people, on_call("Emergency Manager on duty", issued_at))
            if room is None:
                room = IncidentRoom(opened_at=issued_at, opened_by_advisory=n, trigger_asset=r.asset_id,
                                    critical_assets=[r.asset_id], members=people)
                action, text = "open_room", "Incident room opened"
            else:
                room.critical_assets.append(r.asset_id)
                for p in people:
                    _add(room.members, p)
                action, text = "join_room", "Added to incident room"
            alerts.append(Alert(
                advisory=n, issued_at=issued_at, asset_id=r.asset_id, asset_name=asset.name, tier="Critical",
                action=action, recipients=people,
                message=f"{text}: {asset.name} ({r.asset_id}) is Critical ({r.score:.2f}).", reasons=r.reasons))
    return alerts, room
