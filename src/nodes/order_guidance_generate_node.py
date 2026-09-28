"""AgentCore Platform v1.0"""

# Inner subgraph node — LLM-grounded order-quantity recommendation + rationale,
# fusing demand patterns (DemandHistoryRetrieveNode) and event context
# (EventCalendarLookupNode). Trust authenticated once at the outer backbone.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.service import estimate_order_band


class OrderGuidanceGenerateNode(FunctionNode):
    """Generate the recommended order quantity + rationale."""

    # S-1: inner subgraph node — trust authenticated at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm

    @staticmethod
    def _extract_text(raw: Any) -> str:
        # BaseLLM.complete() returns dict {"content": str, ...} for real LLM clients;
        # fake/stub clients in some tests return a bare string. Normalize both, never
        # let a dict leak into a str field.
        if isinstance(raw, dict):
            content = raw.get("content", "")
            return content if isinstance(content, str) else ""
        if isinstance(raw, str):
            return raw
        return ""

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        patterns = state.get("demand_patterns", [])
        events = state.get("event_context", [])
        if not patterns:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["OrderGuidanceGenerateNode: cannot generate guidance without demand patterns"],
            }

        qty_min, qty_max = estimate_order_band(patterns)

        if self._llm is None:
            # Deterministic-core mode: no LLM configured at all — this is the
            # intended fallback path, not an error.
            event_note = f" Event context: {', '.join(events)}." if events else ""
            rationale = (
                f"Based on the last {len(patterns)} demand-history records, "
                f"the recommended order quantity is {qty_min}-{qty_max} units.{event_note}"
            )
        else:
            # LLM IS configured: a failed/empty/malformed call is a real error, not
            # a silent-swallow-to-fallback.
            try:
                raw = self._llm.complete(
                    [
                        {
                            "role": "user",
                            "content": (
                                f"Recommend an order quantity given recent demand patterns "
                                f"{patterns} and event context {events}."
                            ),
                        }
                    ]
                )
            except (TimeoutError, ConnectionError, ValueError) as exc:
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": [f"OrderGuidanceGenerateNode: LLM call failed: {exc}"],
                }
            rationale = self._extract_text(raw)
            if not rationale:
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["OrderGuidanceGenerateNode: LLM returned an empty/unrecognized response"],
                }

        emit_trace_event("order_guidance_generated", {"correlation_id": state.get("correlation_id")}, state)
        return {
            "order_qty_min": qty_min,
            "order_qty_max": qty_max,
            "rationale": rationale,
            "status": AgentStatus.SUCCESS.value,
        }
