"""AgentCore Platform v1.0"""

# Inner subgraph node — retrieves the local event-calendar KB (holidays,
# campaigns) relevant to the query window. Trust authenticated once at the
# outer backbone (S-1 inner-vs-outer rule).

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.service import lookup_event_calendar


class EventCalendarLookupNode(FunctionNode):
    """Look up event-calendar KB entries within the query window."""

    # S-1: inner subgraph node — trust authenticated at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, event_kb: list[dict[str, Any]] | None = None):
        self._event_kb = event_kb or []

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) and raw else {}
        except (ValueError, TypeError):
            payload = {}
        window_days = payload.get("query_window_days", 7) if isinstance(payload, dict) else 7

        events = lookup_event_calendar(self._event_kb, window_days)
        emit_trace_event("event_calendar_looked_up", {"event_count": len(events)}, state)
        return {"event_context": events, "status": AgentStatus.SUCCESS.value}
