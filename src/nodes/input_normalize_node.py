"""AgentCore Platform v1.0"""

# Outer pre_process — parse the NL order-guidance question, S-2 input scan
# (framework @final), and serialize a validated_input JSON envelope for the
# inner subgraph (GraphNode boundary only sees a string — see
# src/graph/graph.py OrderGuidanceGraphNode.extract_input()).

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

DEFAULT_QUERY_WINDOW_DAYS = 7


class InputNormalizeNode(FunctionNode):
    """Parse + normalize the franchise owner's NL order-guidance question."""

    # S-1: outer boundary node — matches agent.yaml required_trust_level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        query = state.get("user_input", "")
        if not isinstance(query, str) or not query.strip():
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["InputNormalizeNode: order-guidance question is empty or missing"],
            }

        normalized_intent = query.strip()
        window_days = DEFAULT_QUERY_WINDOW_DAYS
        validated_input = json.dumps(
            {"query": normalized_intent, "query_window_days": window_days},
            ensure_ascii=False,
        )

        emit_trace_event(
            "input_normalized",
            {"correlation_id": state.get("correlation_id"), "query_window_days": window_days},
            state,
        )
        return {
            "normalized_intent": normalized_intent,
            "query_window_days": window_days,
            "validated_input": validated_input,
            "status": AgentStatus.SUCCESS.value,
        }
