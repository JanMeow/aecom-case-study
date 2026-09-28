"""AI in the incident room: plain questions and slash commands. Answers carry playbook citations."""
from fastapi import APIRouter, HTTPException
from anthropic.types import Message
from backend.api.model import AskRequest, PlaybookRequest, ReportRequest
from backend.ETL.alerts import alerts_until, scores_for
from backend.ETL.extraction import load_advisory
from backend.LLM.model import CitedAnswer
from backend.LLM.service import ask, ask_with_playbooks, get_report
from backend.routers.shared import ASSETS, check_advisory, check_asset

router = APIRouter(prefix="/llm", tags=["llm"])

_REPORTS: dict[tuple[int, str], CitedAnswer] = {}   # (advisory, asset_id) -> briefing; a report takes ~30 s


@router.post("/ask")
async def llm_ask(req: AskRequest) -> CitedAnswer:
    """Plain message in the room: a question about the current situation."""
    check_advisory(req.advisory)
    return await ask(req.question, load_advisory(req.advisory), scores_for(req.advisory, "standard"), ASSETS)


@router.post("/report")
async def llm_report(req: ReportRequest) -> CitedAnswer:
    """/generate_report: situation briefing (PB-04 §4) for an asset, by default the room's trigger asset."""
    check_advisory(req.advisory)
    asset_id = req.asset_id
    if asset_id is None:
        _, room = alerts_until(req.advisory)
        if room is None:
            raise HTTPException(400, "No incident room yet at this advisory; name an asset, e.g. /generate_report SUB-014")
        asset_id = room.trigger_asset
    asset = check_asset(asset_id)
    key = (req.advisory, asset_id)
    if key not in _REPORTS:
        _REPORTS[key] = await get_report(asset, scores_for(req.advisory, "standard")[asset_id], load_advisory(req.advisory))
    return _REPORTS[key]


@router.post("/playbook")
async def llm_playbook(req: PlaybookRequest) -> CitedAnswer:
    """/playbook: what the playbooks say about one asset."""
    return await ask_with_playbooks(req.question, check_asset(req.asset_id))
