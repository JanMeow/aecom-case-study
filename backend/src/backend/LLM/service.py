"""
Calls to Claude. Prompt wording lives in prompt.py; playbook documents and citation parsing in playbook.py.
"""
from anthropic import AsyncAnthropic
from backend.config.setting import anthropic_api_key
from backend.LLM.model import CitedAnswer
from backend.ETL.model import Advisory, AggregatedData, RiskResult
from backend.LLM.prompt import (QA_SYSTEM, QA_GENERAL_SYSTEM, REPORT_SYSTEM, build_playbook_context, build_report_context,
                               build_room_context)

from backend.LLM.playbook import parse_cited_answer, playbook_documents

# max_tokens is a ceiling, not a target (only generated tokens are paid for); length is set in the prompts
_MAX_TOKENS_REPORT = 4000
_MAX_TOKENS_QA = 1500
_MODEL = "claude-opus-5-5"

# async client: the API awaits it without blocking other requests
client = AsyncAnthropic(api_key=anthropic_api_key)


async def ask_with_playbooks(question: str, asset: AggregatedData) -> CitedAnswer:
    """Ask Claude a question about an asset, grounded in the playbooks; returns the answer and verifiable citations.

    e.g. await ask_with_playbooks("PS-007 lost utility power. What should Water Ops do?", assets["PS-007"])
    """
    prompt = f"{build_playbook_context(asset)}\n\n{question}".strip()
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS_QA,
        system=QA_SYSTEM,
        messages=[{"role": "user", "content": [*playbook_documents(), {"type": "text", "text": prompt}]}],
    )
    return _finish(response)


# ---------------------------------------------------------------------------
async def get_report(asset: AggregatedData, risk: RiskResult, advisory: Advisory | None = None) -> CitedAnswer:
    """Situation briefing for one asset (structure from PB-04 §4), with playbook citations for the actions."""
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS_REPORT,
        system=REPORT_SYSTEM,
        messages=[{"role": "user", "content": [
            *playbook_documents(), {"type": "text", "text": build_report_context(asset, risk, advisory)}]}],
    )
    return _finish(response)


def _finish(response) -> CitedAnswer:
    """Parse the answer and its citations; flag it if it was cut off by max_tokens."""
    answer = parse_cited_answer(response.content)
    if response.stop_reason == "max_tokens":
        answer.text += "\n\n(truncated: the answer reached the length limit)"
    return answer


async def ask(question: str, advisory: Advisory, risks: dict[str, RiskResult],
              assets: dict[str, AggregatedData]) -> CitedAnswer:
    """General question in the incident room, grounded in the current situation and the playbooks.

    Context: the storm now, every High/Critical asset, and the full record of any asset named in the question.
    e.g. await ask("What happens if SUB-014 fails?", advisory, scores_for(24, "standard"), assets)
    """
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS_QA,
        system=QA_GENERAL_SYSTEM,
        messages=[{"role": "user", "content": [ {"type": "text", "text": build_room_context(question, advisory, risks, assets)}]}],
    )
    return _finish(response)


if __name__ == "__main__":
    import asyncio

    from backend.ETL.alerts import scores_for
    from backend.ETL.extraction import load_advisory, load_processed_assets

    key, advisory = "SUB-014", 24          # the asset and advisory that open the incident room
    assets = load_processed_assets()
    risk = scores_for(advisory, "standard")[key]
    asset = assets[key]

    question = "A pumping station's feeding substation is rated High or Critical, any suggestion?"
    response = asyncio.run(get_report(asset, risk, load_advisory(advisory)))
    # response = asyncio.run(ask_with_playbooks(question, asset))   # async function: run it to completion
    print(response.text)
    for c in response.citations:
        print(c.label, "->", c.cited_text[:80].replace("\n", " "))
