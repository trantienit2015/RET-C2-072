"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict — never Pydantic BaseModel.
# LangGraph checkpoints use msgpack serialization; Pydantic objects
# cause silent corruption. Extend AgentState with agent-specific
# fields only. Do NOT add credentials, secrets, or Pydantic models.

from typing import NotRequired

from framework.schemas.agent_state import AgentState


# Type-check note: the wheel ships no py.typed, so mypy resolves AgentState to Any
# and reports every NotRequired below as valid-type. The fields are correct (the state
# contract requires NotRequired) -- the report is a packaging artifact, suppressed per field.
# Drop these ignores once the wheel ships py.typed.
class State(AgentState):
    """RET-C2-072 Retail Demand Forecast Q&A & Replenishment Guidance Agent state.

    All shared fields (user_input, status, session_id, node_history,
    error_log, hitl_*, etc.) are inherited from AgentState.
    """

    # Outer pre_process (InputNormalizeNode)
    normalized_intent: NotRequired[str]  # type: ignore[valid-type]
    query_window_days: NotRequired[int]  # type: ignore[valid-type]

    # Inner subgraph (EventCalendarLookupNode / DemandHistoryRetrieveNode /
    # OrderGuidanceGenerateNode / ConfidenceBandFormatNode) — merged back via
    # OrderGuidanceGraphNode.merge_output()
    event_context: NotRequired[list[str]]  # type: ignore[valid-type]
    demand_patterns: NotRequired[list[dict]]  # type: ignore[valid-type]
    order_qty_min: NotRequired[int]  # type: ignore[valid-type]
    order_qty_max: NotRequired[int]  # type: ignore[valid-type]
    confidence_pct: NotRequired[int]  # type: ignore[valid-type]
    rationale: NotRequired[str]  # type: ignore[valid-type]
    confidence_band: NotRequired[str]  # type: ignore[valid-type]

    # Outer post_process (HITLDisclaimerGateNode)
    disclaimer_text: NotRequired[str]  # type: ignore[valid-type]
    final_guidance: NotRequired[str]  # type: ignore[valid-type]
