"""The report the investigation agent must end every turn with.

The Pydantic model is the acceptance test of the instructions: whatever the model answers is parsed into it, and a
turn whose answer does not fit is an error, not a report.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """One fact the conclusion rests on."""

    source: Literal["sentry", "github", "other"] = Field(description="Where this fact comes from: 'sentry' for an error or event, 'github' for code, 'other' for anything else.")
    reference: str = Field(description="A stable pointer to the fact: a Sentry issue or event URL, a GitHub file URL at a commit, or another identifier.")
    proves: str = Field(description="What exactly this fact proves, in one sentence, e.g. 'KeyError: UK raised in shop/shipping.py rate_for'.")


class InvestigationReport(BaseModel):
    """The structured answer to one investigation question."""

    summary: str = Field(description="One or two sentences: what is failing, for which input, and why. The conclusion of the whole report.")
    exception: str | None = Field(description="The exception as the error tracker shows it, e.g. \"KeyError: 'UK'\", or null if the question is not about an exception.")
    file: str | None = Field(description="Repository-relative path of the file responsible for the defect, e.g. 'sample-app/shop/shipping.py', or null if no single file is responsible.")
    symbol: str | None = Field(description="The function, method or class in `file` where the defect lives, e.g. 'rate_for', or null if it is not one symbol.")
    root_cause: str = Field(description="The defect as a fact about the code: quote the responsible line or behaviour and say why it is wrong for the failing input.")
    confidence: Literal["low", "medium", "high"] = Field(
        description="How much of the report you verified against the error, the event and the code: 'high' when they agree, 'medium' when part is inferred, 'low' when little could be verified."
    )
    evidence: list[Evidence] = Field(description="Every fact the conclusion rests on, each with its `source`, `reference` and `proves`. Empty only when nothing could be verified.")
    next_check: str | None = Field(
        description="The single most useful thing to check next when the report is incomplete, e.g. 'read event 4f2a91 in Sentry to confirm the release', or null when the investigation is complete."
    )
