"""Ask one investigation question and print the report readably.

Usage: python ask.py [--served] [--json] "question"   (`--served` asks the agent `agents serve` runs.)
"""

import argparse
import asyncio
import json
import sys

from investigate import Investigation, investigate, served_agent
from main import build_agent


def render(outcome: Investigation) -> str:
    """The report as a readable block: conclusion, evidence, root cause, and the tool calls the turn made."""
    lines: list[str] = []
    report = outcome.report
    if report is None:
        lines.append(f"No report: {outcome.error}")
    else:
        lines.append(report.summary)
        if report.exception:
            lines.append(f"Exception: {report.exception}")
        if report.file:
            where = f"File: {report.file}"
            if report.symbol:
                where += f"  Symbol: {report.symbol}"
            lines.append(where)
        lines.append(f"Confidence: {report.confidence}")
        lines.append("")
        lines.append(f"Root cause: {report.root_cause}")
        if report.evidence:
            lines.append("")
            lines.append("Evidence:")
            for item in report.evidence:
                lines.append(f"  [{item.source}] {item.reference} — {item.proves}")
        if report.next_check:
            lines.append("")
            lines.append(f"Next check: {report.next_check}")
    if outcome.tool_calls:
        lines.append("")
        lines.append("Tool calls:")
        for call in outcome.tool_calls:
            lines.append(f"  {call.name}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the investigation agent one question.")
    parser.add_argument("question", help="the investigation question")
    parser.add_argument("--served", action="store_true", help="ask the served agent instead of the in-process one")
    parser.add_argument("--json", action="store_true", help="print the raw report as JSON")
    args = parser.parse_args()

    agent = served_agent() if args.served else build_agent()
    outcome = asyncio.run(investigate(args.question, agent=agent))
    if args.json:
        payload = outcome.report.model_dump() if outcome.report is not None else {"error": outcome.error}
        print(json.dumps(payload, indent=2))
    else:
        print(render(outcome))
    sys.exit(0 if outcome.ok else 1)


if __name__ == "__main__":
    main()
