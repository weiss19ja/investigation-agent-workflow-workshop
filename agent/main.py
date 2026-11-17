"""The investigation agent: model, instructions, and the report as its output contract.

Built through `build_agent()` so tests can run it with a scripted model and no connectors; nothing runs at import time
(the SDK's CLI imports `main:agent` at module scope).
"""

import os
from pathlib import Path

import mistralai.agents as agents

from report import InvestigationReport

ROOT = Path(__file__).resolve().parent
MODEL = "mistral-large-4"
DEFAULT_AGENT_NAME = os.environ.get("INVESTIGATION_AGENT_NAME", "investigation-agent")


def build_agent(*, connectors: bool = True, name: str | None = None) -> agents.Agent:
    """Build the investigation agent.

    `connectors` has no effect yet; module 2 gives it one. `name` defaults to `INVESTIGATION_AGENT_NAME` from the
    environment, else `investigation-agent`.
    """
    return agents.Agent(
        name=name or DEFAULT_AGENT_NAME,
        model=MODEL,
        description="Answers one investigation question with a validated InvestigationReport.",
        instructions=(ROOT / "instructions.md").read_text(encoding="utf-8"),
        output_type=InvestigationReport,
        max_iterations=32,
        temperature=0.1,
    )


agent = build_agent()
