"""The investigation agent: model, instructions, connectors, skills, policy, hooks, and the report as its output contract.

Built through `build_agent()` so tests can run it with a scripted model and no connectors; nothing runs at import time
(the SDK's CLI imports `main:agent` at module scope).
"""

import os
from pathlib import Path

import mistralai.agents as agents

from config import GITHUB_CONNECTOR_NAME, SENTRY_CONNECTOR_NAME, permission_policy
from hooks import AuditTrail
from report import InvestigationReport

ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "skills"
MODEL = "mistral-large-4"
DEFAULT_AGENT_NAME = os.environ.get("INVESTIGATION_AGENT_NAME", "investigation-agent")


def build_agent(*, connectors: bool = True, name: str | None = None) -> agents.Agent:
    """Build the investigation agent.

    `connectors=True` attaches the Sentry and GitHub Studio connectors named by the environment; `False` builds the
    connector-less twin the tests run with a scripted model. `name` defaults to `INVESTIGATION_AGENT_NAME` from the
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
        environment=agents.BashkitSandbox(access="none"),
        skills=[agents.LocalSkillBundle.from_directory(path) for path in sorted(SKILLS_DIR.iterdir()) if path.is_dir()],
        connectors=(
            [
                agents.connector(SENTRY_CONNECTOR_NAME, run_as="auto", auto_auth=False),
                agents.connector(GITHUB_CONNECTOR_NAME, run_as="auto", auto_auth=False),
            ]
            if connectors
            else []
        ),
        permission_policy=permission_policy(SENTRY_CONNECTOR_NAME, GITHUB_CONNECTOR_NAME),
        hooks=[AuditTrail()],
        builtins=agents.Builtins(subagents=False),
    )


agent = build_agent()
