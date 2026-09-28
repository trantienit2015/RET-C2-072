"""AgentCore Platform v1.0"""

# Inner subgraph node — formats the confidence band string from the order
# quantity band produced by OrderGuidanceGenerateNode. Trust authenticated
# once at the outer backbone.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

DEFAULT_CONFIDENCE_PCT = 80


class ConfidenceBandFormatNode(FunctionNode):
    """Format the order-quantity band + confidence percentage."""

    # S-1: inner subgraph node — trust authenticated at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        qty_min = state.get("order_qty_min")
        qty_max = state.get("order_qty_max")
        if qty_min is None or qty_max is None:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ConfidenceBandFormatNode: missing order quantity band to format"],
            }

        confidence_pct = DEFAULT_CONFIDENCE_PCT
        confidence_band = f"{qty_min}-{qty_max} units, {confidence_pct}% confidence"

        emit_trace_event("confidence_band_formatted", {"confidence_pct": confidence_pct}, state)
        return {
            "confidence_band": confidence_band,
            "confidence_pct": confidence_pct,
            "status": AgentStatus.SUCCESS.value,
        }
