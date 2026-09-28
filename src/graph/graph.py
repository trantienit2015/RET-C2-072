"""AgentCore Platform v1.0"""

# RET-C2-072 — Retail Demand Forecast Q&A & Replenishment Guidance Agent
#
# Cat 2 — outer AgentBaseGraph (fixed 5-node backbone) + GraphNode in the
# `main` slot wrapping the inner OrderGuidanceWorkflowGraph domain workflow.
# The GraphNode class MUST
# live in this file (NOT under src/nodes/), so PB-6 (test_pb_invoke_order.py,
# which auto-discovers every BaseNode subclass under src/nodes/) does not pick
# it up and mis-assert the standard node lifecycle on it.

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.nodes.hitl_disclaimer_gate_node import HITLDisclaimerGateNode
from src.nodes.input_normalize_node import InputNormalizeNode
from src.schemas.state import State
from src.services.service import DEFAULT_TOP_K, resolve_top_k


class OrderGuidanceGraphNode(GraphNode):
    """Wraps the inner order-guidance domain workflow (event/demand/guidance/band)."""

    # S-1: outer main-slot wrapper — first node in outer backbone receiving caller
    # input after pre_process; matches agent.yaml required_trust_level and the
    # sibling outer FunctionNodes (input_normalize / hitl_disclaimer_gate).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def __init__(
        self,
        event_kb: list[dict[str, Any]] | None = None,
        demand_kb: list[dict[str, Any]] | None = None,
        llm: Any = None,
        top_k: Any = DEFAULT_TOP_K,
    ):
        super().__init__()
        self._event_kb = event_kb or []
        self._demand_kb = demand_kb or []
        self._llm = llm
        self._top_k = resolve_top_k(top_k)

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import OrderGuidanceWorkflowGraph

        sg = OrderGuidanceWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() — audit the dispatch into the inner subgraph.
        emit_trace_event("order_guidance_dispatched", {"correlation_id": state.get("correlation_id")}, state)
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        # S-4: runs inside GraphNode.execute() — audit the subgraph outcome merged back out.
        emit_trace_event(
            "order_guidance_completed",
            {"confidence_pct": sub_result.get("confidence_pct")},
            state,
        )
        return {
            "event_context": sub_result.get("event_context", []),
            "demand_patterns": sub_result.get("demand_patterns", []),
            "order_qty_min": sub_result.get("order_qty_min"),
            "order_qty_max": sub_result.get("order_qty_max"),
            "confidence_pct": sub_result.get("confidence_pct"),
            "rationale": sub_result.get("rationale", ""),
            "confidence_band": sub_result.get("confidence_band", ""),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {"event_kb": self._event_kb, "demand_kb": self._demand_kb, "llm": self._llm, "top_k": self._top_k}


class Graph(AgentBaseGraph):
    """Outer graph — fixed backbone: initialize -> pre_process -> main(GraphNode) -> post_process -> finalize."""

    @property
    def name(self) -> str:
        return "ret-c2-072"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode
        event_kb = self.config.get("event_kb", [])
        demand_kb = self.config.get("demand_kb", [])
        llm = self.config.get("llm")
        top_k = self.config.get("top_k", DEFAULT_TOP_K)
        self._nodes["pre_process"] = InputNormalizeNode()
        self._nodes["main"] = OrderGuidanceGraphNode(event_kb=event_kb, demand_kb=demand_kb, llm=llm, top_k=top_k)
        self._nodes["post_process"] = HITLDisclaimerGateNode()

    # add_edges() is intentionally not overridden (default backbone wiring).
