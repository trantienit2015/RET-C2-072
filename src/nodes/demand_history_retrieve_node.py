"""AgentCore Platform v1.0"""

# Inner subgraph node — deterministic recency-window lookup over the
# demand-summary KB (most-recent-first date sort, no semantic/keyword ranking;
# rolling 90-day+ window, operator-managed). Trust authenticated once at the
# outer backbone (S-1 inner-vs-outer rule).

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.service import DEFAULT_TOP_K, resolve_top_k, retrieve_demand_patterns


class DemandHistoryRetrieveNode(FunctionNode):
    """Retrieve recent demand patterns from the demand-summary KB."""

    # S-1: inner subgraph node — trust authenticated at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, demand_kb: list[dict[str, Any]] | None = None, top_k: Any = DEFAULT_TOP_K):
        self._demand_kb = demand_kb or []
        self._top_k = resolve_top_k(top_k)

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) and raw else {}
        except (ValueError, TypeError):
            payload = {}
        if not isinstance(payload, dict) or not payload.get("query"):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["DemandHistoryRetrieveNode: no order-guidance query in inner input"],
            }

        patterns = retrieve_demand_patterns(self._demand_kb, top_k=self._top_k)
        if not patterns:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["DemandHistoryRetrieveNode: demand-summary KB has no data for this query"],
            }

        emit_trace_event("demand_history_retrieved", {"pattern_count": len(patterns)}, state)
        return {"demand_patterns": patterns, "status": AgentStatus.SUCCESS.value}
