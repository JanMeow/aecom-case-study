"""
Data models for the AI service (LLM/service.py).

PlaybookSection  one citable ## section of a playbook
Citation         one playbook passage an answer relies on, returned by the API's Citations feature
CitedAnswer      an AI answer with its citations
"""
from pydantic import BaseModel, Field


class PlaybookSection(BaseModel):
    """One ## section of a playbook: the smallest thing the AI can cite."""
    playbook_id: str                        # e.g. "PB-02"
    section: str                            # e.g. "7" (from "## 7. Known issues")
    heading: str                            # e.g. "Known issues"
    text: str                               # the section, heading included


class Citation(BaseModel):
    playbook_id: str                        # e.g. "PB-02"
    section: str                            # e.g. "7"
    label: str                              # e.g. "[PB-02 §7]", shown in the UI
    cited_text: str                         # the exact passage the answer relies on (returned by the API)


class CitedAnswer(BaseModel):
    text: str                               # answer with [PB-xx §n] markers after each cited sentence
    citations: list[Citation] = Field(default_factory=list)   # unique, in order of first use
    model: str | None = None                # which model produced the answer
