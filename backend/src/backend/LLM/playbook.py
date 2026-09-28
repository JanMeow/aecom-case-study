"""
Playbooks as citable documents for Claude.

Playbooks are sent as documents with Anthropic's built-in Citations: the API returns the exact passage each
part of the answer relies on, so every citation is verifiable. With only 5 short playbooks no retrieval is
needed; each playbook is split into its "## " sections only so a citation can point at one section.

    load_playbooks()       read and split the playbooks
    playbook_documents()   the document blocks to send to the API
    parse_cited_answer()   answer text + [PB-xx §n] citations from the API response
"""
import re
from functools import lru_cache
from pathlib import Path

from backend.LLM.model import Citation, CitedAnswer, PlaybookSection

PLAYBOOKS = Path(__file__).parents[1] / "data" / "sources" / "plans"


@lru_cache
def load_playbooks() -> dict[str, list[PlaybookSection]]:
    """Every playbook split into its sections: playbook_id -> [section, ...] (read once, then cached).

    "## 7. Known issues" becomes PlaybookSection(playbook_id="PB-02", section="7", heading="Known issues", ...).
    The front matter (--- id / title ... ---) and the "# title" line are dropped.
    """
    playbooks = {}
    for path in sorted(PLAYBOOKS.glob("PB-*.md")):
        text = path.read_text()
        body = text.split("---", 2)[2] if text.startswith("---") else text     # drop front matter
        playbook_id = path.name.split("_")[0]                                   # "PB-02_pumping..." -> "PB-02"
        sections = []
        for part in re.split(r"\n(?=## )", body):
            m = re.match(r"## (\d+)\.\s*(.+)", part.strip())
            if m:                                                               # skips the "# title" part
                sections.append(PlaybookSection(playbook_id=playbook_id, section=m.group(1),
                                                heading=m.group(2).strip(), text=part.strip()))
        playbooks[playbook_id] = sections
    return playbooks


def _title(playbook_id: str) -> str:
    path = next(PLAYBOOKS.glob(f"{playbook_id}_*.md"))
    return re.search(r"^title:\s*(.+)$", path.read_text(), re.M).group(1).strip()


def playbook_documents() -> list[dict]:
    """The playbooks as API document blocks, citations on, one content block per section.

    The same documents go at the start of every call, so the last one carries cache_control: after the first
    call they are read from the prompt cache (faster and cheaper).
    """
    docs = []
    for playbook_id, sections in load_playbooks().items():
        docs.append({
            "type": "document",
            "title": f"{playbook_id} {_title(playbook_id)}",
            "source": {"type": "content", "content": [{"type": "text", "text": s.text} for s in sections]},
            "citations": {"enabled": True},
        })
    docs[-1]["cache_control"] = {"type": "ephemeral"}
    return docs


def parse_cited_answer(content) -> CitedAnswer:
    """Turn the response's content blocks into answer text with [PB-xx §n] markers, plus the citation list.

    Each cited text block carries citations of type "content_block_location":
    document_index (which playbook), start_block_index (which section), cited_text (the exact passage).
    """
    ids = list(load_playbooks())
    parts, citations, seen = [], [], set()
    for block in content:
        if block.type != "text":
            continue
        labels = []
        for c in getattr(block, "citations", None) or []:
            if c.type != "content_block_location":
                continue
            playbook_id = ids[c.document_index]
            section = load_playbooks()[playbook_id][c.start_block_index].section
            label = f"[{playbook_id} §{section}]"
            if label not in labels:
                labels.append(label)
            if label not in seen:
                seen.add(label)
                citations.append(Citation(playbook_id=playbook_id, section=section, label=label,
                                          cited_text=c.cited_text.strip()))
        parts.append(block.text + (" " + " ".join(labels) if labels else ""))
    return CitedAnswer(text="".join(parts).strip(), citations=citations)
