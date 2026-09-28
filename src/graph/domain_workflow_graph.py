"""AgentCore Platform v1.0"""

# Inner subgraph (Cat 2) — domain workflow wrapped by OrderGuidanceGraphNode
# in the outer graph's `main` slot.

from typing import Any
from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from src.nodes.confidence_band_format_node import ConfidenceBandFormatNode
from src.nodes.demand_history_retrieve_node import DemandHistoryRetrieveNode
from src.nodes.event_calendar_lookup_node import EventCalendarLookupNode
from src.nodes.order_guidance_generate_node import OrderGuidanceGenerateNode
from src.schemas.state import State
from src.services.service import DEFAULT_TOP_K


class OrderGuidanceWorkflowGraph(BaseGraph):
    """Inner domain workflow: event-lookup -> demand-retrieve -> guidance-generate -> band-format."""

    @property
    def name(self) -> str:
        return "order_guidance_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        pass

    def register_nodes(self) -> None:  # noqa: D102 — no super(); no initialize/finalize
        event_kb = self.config.get("event_kb", []) if hasattr(self, "config") else []
        demand_kb = self.config.get("demand_kb", []) if hasattr(self, "config") else []
        llm = self.config.get("llm") if hasattr(self, "config") else None
        top_k = self.config.get("top_k", DEFAULT_TOP_K) if hasattr(self, "config") else DEFAULT_TOP_K
        self._nodes["event_calendar_lookup"] = EventCalendarLookupNode(event_kb=event_kb)
        self._nodes["demand_history_retrieve"] = DemandHistoryRetrieveNode(demand_kb=demand_kb, top_k=top_k)
        self._nodes["order_guidance_generate"] = OrderGuidanceGenerateNode(llm=llm)
        self._nodes["confidence_band_format"] = ConfidenceBandFormatNode()

    def add_edges(self) -> None:
        self._sg.add_edge(START, "event_calendar_lookup")
        self._sg.add_edge("event_calendar_lookup", "demand_history_retrieve")
        self._sg.add_edge("demand_history_retrieve", "order_guidance_generate")
        self._sg.add_edge("order_guidance_generate", "confidence_band_format")
        self._sg.add_edge("confidence_band_format", END)

    def route(self, state: AgentState) -> str:  # required by ABC (linear — not called)
        return END if state.get("status") == AgentStatus.ERROR.value else "confidence_band_format"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "event_context": state.get("event_context", []),
            "demand_patterns": state.get("demand_patterns", []),
            "order_qty_min": state.get("order_qty_min"),
            "order_qty_max": state.get("order_qty_max"),
            "confidence_pct": state.get("confidence_pct"),
            "rationale": state.get("rationale", ""),
            "confidence_band": state.get("confidence_band", ""),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
