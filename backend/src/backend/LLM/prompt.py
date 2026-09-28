"""
All prompt wording in one place: system prompts and the context sent with each request.
"""
import re

from backend.ETL.model import Advisory, AggregatedData, RiskResult

# Situation briefing: structure follows PB-04 §4 ("A briefing must cover ...")
REPORT_SYSTEM = (
    "Write the situation briefing for SGW's incident room, under 400 words. "
    "Use exactly these sections, from PB-04 §4: "
    "1) Storm position and forecast, "
    "2) Assets at High/Critical risk, with customers and critical facilities affected, "
    "3) Dependencies (power -> water), "
    "4) Recommended actions, each with an owner, "
    "5) Resources (crews, generators, fuel). "
    "Take every number and rating from the data provided; do not re-rate risk or invent figures. "
    "If something is not in the data, say so. "
    "Ground every recommended action in the playbooks, citing the passage it comes from. Recommend; people decide."
)

# Questions in the incident room
QA_SYSTEM = (
    "You support SGW's incident room during a storm. Answer from the data and playbooks provided, "
    "in 3-6 sentences or bullets. Take every number from the data. "
    "Ground recommendations in the playbooks, citing the passage they come from. People decide."
)

QA_GENERAL_SYSTEM = (
    "You support SGW's incident room during a storm. Answer from the data"
)
# Fields left out of asset records: long and not useful to the model
_ASSET_EXCLUDE = {"field_events", "path"}


def build_report_context(asset: AggregatedData, risk: RiskResult, advisory: Advisory | None = None) -> str:
    """Facts for the briefing: the storm (if given), the asset record and its risk assessment."""
    parts = []
    if advisory:
        parts.append(
            f"Storm: Hurricane Ian, NHC advisory {advisory.advisory} issued "
            f"{advisory.issued_at:%d %b %Y %H:%M} UTC. Centre {advisory.center.lat}N "
            f"{abs(advisory.center.lon)}W, max sustained wind {advisory.max_wind_kt} kt, "
            f"{f'Category {advisory.category} hurricane' if advisory.category else 'tropical storm'}."
        )
    else:
        parts.append("Storm: no advisory data provided.")
    parts.append(f"Asset record: {asset.model_dump_json(exclude=_ASSET_EXCLUDE)}")
    parts.append(f"Risk assessment (rules score, drives alerts): {risk.model_dump_json()}")
    parts.append("Write the situation briefing.")
    return "\n\n".join(parts)


def build_playbook_context(asset: AggregatedData) -> str:
    """Facts for a question about one asset: its aggregated record."""
    return f"Asset record: {asset.model_dump_json(exclude=_ASSET_EXCLUDE)}"


def build_room_context(question: str, advisory: Advisory, risks: dict[str, RiskResult],
                       assets: dict[str, AggregatedData]) -> str:
    """Facts for a general question in the incident room: the storm, every asset at High or Critical risk
    (short summary), and the full record of any asset the question mentions by ID (e.g. "SUB-014")."""
    at_risk = sorted((r for r in risks.values() if r.tier in ("High", "Critical")), key=lambda r: -r.score)
    lines = [f"- {r.asset_id} {assets[r.asset_id].name} ({assets[r.asset_id].type}): {r.tier} {r.score:.2f}, "
             f"likelihood {r.likelihood:.0%}, depends on {r.depends_on or '-'}, "
             f"{r.customers_affected:,} customers, facilities {', '.join(r.critical_facilities) or '-'}"
             for r in at_risk]
    parts = [
        f"Storm: Hurricane Ian, NHC advisory {advisory.advisory} issued {advisory.issued_at:%d %b %Y %H:%M} UTC. "
        f"Centre {advisory.center.lat}N {abs(advisory.center.lon)}W, max sustained wind {advisory.max_wind_kt} kt.",
        "Assets at High or Critical risk (rules score):\n" + ("\n".join(lines) or "none"),
    ]
    for asset_id in sorted(set(re.findall(r"\b[A-Z]{2,4}-\d{3}\b", question.upper())) & set(assets)):
        parts.append(f"Record for {asset_id}: {assets[asset_id].model_dump_json(exclude=_ASSET_EXCLUDE)}\n"
                     f"Risk for {asset_id}: {risks[asset_id].model_dump_json()}")
    parts.append(f"Question: {question}")
    return "\n\n".join(parts)
