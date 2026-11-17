"""The audit trail: log every tool call the agent makes, before it runs. Argument values are never logged."""

import logging

import mistralai.agents as agents

logger = logging.getLogger("investigation.audit")


class AuditTrail(agents.Hook):
    """Logs `tool call <tool_id>(<sorted argument names>) in session <id>` at INFO on `pre_tool_call`, then continues."""

    async def pre_tool_call(self, ctx: agents.HookCallbackContext, call: agents.hook.PreToolCall) -> None:
        arguments = ", ".join(sorted(call.arguments))
        logger.info(f"tool call {call.tool_id}({arguments}) in session {ctx.session.id}")
        return None
