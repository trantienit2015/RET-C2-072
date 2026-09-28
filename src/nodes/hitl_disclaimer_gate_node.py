"""AgentCore Platform v1.0"""

# Outer post_process — assembles the final order-guidance answer and attaches
# a NON-SUPPRESSIBLE HITL disclaimer (S-3): the human always places the final
# order. This is a deterministic assertion node, NOT a D6 interrupt()/pause
# HITL pattern — config cannot disable the disclaimer; suppression is
# re-checked in _extra_security_gate_output() and returns a FAIL, not a raise.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

DISCLAIMER_JA = "これは参考数値です。最終的な発注量はご自身でご判断ください。"


class HITLDisclaimerGateNode(FunctionNode):
    """Attach the non-suppressible HITL disclaimer to the final guidance."""

    # S-1: outer boundary node — matches agent.yaml required_trust_level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        confidence_band = state.get("confidence_band", "")
        rationale = state.get("rationale", "")
        if not confidence_band:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["HITLDisclaimerGateNode: missing confidence band before disclaimer gate"],
            }

        final_guidance = f"{rationale}\n\n{confidence_band}\n\n{DISCLAIMER_JA}"

        emit_trace_event("hitl_disclaimer_attached", {"correlation_id": state.get("correlation_id")}, state)
        return {
            "disclaimer_text": DISCLAIMER_JA,
            "final_guidance": final_guidance,
            "formatted_output": final_guidance,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-3 non-suppressible re-check: verify the disclaimer is present in this node's own output."""
        final_guidance = state.get("final_guidance", "")
        if DISCLAIMER_JA not in final_guidance:
            emit_trace_event("hitl_disclaimer_suppression_blocked", {}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["HITLDisclaimerGateNode: S-3 re-check blocked a suppressed HITL disclaimer"],
            }
        return state
