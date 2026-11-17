"""Run one investigation turn as data: a session, a question, and the record read into an `Investigation`.

Nothing here raises for a bad answer: an invalid report, a failed turn, a blocked turn, and a turn without a final
answer all become `report=None` with a sentence in `error`.
"""

from dataclasses import dataclass, field

import mistralai.agents as agents

from main import DEFAULT_AGENT_NAME
from report import InvestigationReport


@dataclass
class Investigation:
    """The outcome of one turn: the question, the session it ran in, and what came back."""

    question: str
    session_id: str | None
    report: InvestigationReport | None
    text: str
    tool_calls: tuple[agents.ToolCall, ...] = field(default_factory=tuple)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.report is not None and self.error is None


async def investigate(question: str, *, agent: agents.Agent, timeout: float = 600) -> Investigation:
    """Ask `question` on a fresh session of `agent` and read the turn record into an `Investigation`."""
    session = await agent.start_session()
    try:
        state = await session.run(question, output_type=InvestigationReport, timeout=timeout)
        return _record(question, state)
    finally:
        await session.cancel()


def served_agent(name: str | None = None) -> agents.Agent:
    """The agent `agents serve` runs, loaded by name from the workspace."""
    return agents.Agent.load_from(agent_name=name or DEFAULT_AGENT_NAME)


def _record(question: str, state: agents.TurnState) -> Investigation:
    base = {
        "question": question,
        "session_id": state.session_id,
        "text": state.text,
        "tool_calls": state.tool_calls,
    }
    match state:
        case agents.Completed(output=InvestigationReport() as report):
            return Investigation(report=report, error=None, **base)
        case agents.Completed(output=agents.InvalidOutput(error=error)):
            return Investigation(report=None, error=f"Answer is not a valid InvestigationReport: {error}", **base)
        case agents.Completed():
            return Investigation(report=None, error=f"Turn ended without a final report (stop_reason={state.stop_reason!r}).", **base)
        case agents.Failed(error=error):
            return Investigation(report=None, error=f"Turn failed: {error}", **base)
        case agents.Blocked():
            return Investigation(report=None, error="Turn is blocked, waiting on an approval or a client tool.", **base)
        case agents.Running():
            return Investigation(report=None, error="Turn did not finish within the timeout.", **base)
        case agents.Busy():
            return Investigation(report=None, error="Another turn is already running on this session.", **base)
        case _:
            return Investigation(report=None, error=f"Unexpected turn state: {state!r}", **base)
