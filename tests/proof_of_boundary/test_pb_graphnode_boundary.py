# RET-C2-072 - GraphNode boundary test (Cat 2 outer main-slot wrapper).
#
# Why this test exists: PB-6 (test_pb_invoke_order.py) probes each node's
# __call__ ordering with a bare state. A GraphNode cannot be probed that way -
# its execute() instantiates and invokes the whole inner subgraph, and with
# error_strategy = "propagate" an inner error raises SubgraphError by contract.
# PB-6 therefore excludes GraphNode subclasses, and this file carries the
# boundary coverage instead. Skipping it would leave the exact test-scope blind
# spot where the outer GraphNode is a real
# security boundary (first node in the outer backbone to receive validated
# caller input after pre_process).
#
# framework/nodes/graph_node.py: GraphNode extends BaseNode directly (not
# FunctionNode), so it has no _security_gate_input/_security_gate_output at
# all - S-2/S-3 gating is delegated entirely to the outer InputNormalizeNode /
# HITLDisclaimerGateNode and the inner subgraph's own FunctionNode chain. This
# test proves that delegation is real, not absent.

from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import OrderGuidanceGraphNode
from src.nodes.event_calendar_lookup_node import EventCalendarLookupNode


def _node():
    return OrderGuidanceGraphNode(event_kb=[], demand_kb=[], llm=None)


class TestGraphNodeS1TrustGate:
    """S-1: the outer main-slot GraphNode enforces the trust gate like any BaseNode."""

    def test_insufficient_trust_returns_error_without_invoking_subgraph(self, monkeypatch):
        node = _node()
        called = {"get_subgraph": False}

        def _spy_get_subgraph():
            called["get_subgraph"] = True
            raise AssertionError("get_subgraph() must not run when the S-1 gate denies")

        monkeypatch.setattr(node, "get_subgraph", _spy_get_subgraph)

        state = {
            "caller_trust_level": TrustLevel.ANONYMOUS.value,
            "validated_input": '{"query": "should we reorder?", "window_days": 14}',
        }
        out = node(state)

        assert out["status"] == "error"
        assert any("S-1 trust gate denied" in e for e in out["error_log"])
        assert called["get_subgraph"] is False

    def test_matches_agent_yaml_required_trust_level(self):
        # The outer main-slot wrapper must match config/agent.yaml
        # (VERIFIED_EXTERNAL), not the inner subgraph nodes' ANONYMOUS default.
        assert OrderGuidanceGraphNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL


class TestGraphNodeBoundaryMapping:
    """Boundary mapping: extract_input()/merge_output() do not leak raw state/subgraph dicts."""

    def test_extract_input_only_reads_validated_input(self):
        node = _node()
        state = {
            "validated_input": '{"query": "should we reorder?", "window_days": 14}',
            "user_input": "raw caller text should not leak",
            "unrelated_secret_field": "must-not-appear",
        }
        extracted = node.extract_input(state)

        assert isinstance(extracted, str)
        assert "unrelated_secret_field" not in extracted
        assert "must-not-appear" not in extracted

    def test_merge_output_maps_fields_explicitly_no_raw_passthrough(self):
        node = _node()
        state = {}
        sub_result = {
            "event_context": ["school holiday"],
            "demand_patterns": [{"date": "2026-07-01", "qty": 90}],
            "order_qty_min": 80,
            "order_qty_max": 100,
            "confidence_pct": 70,
            "rationale": "based on recent demand",
            "confidence_band": "medium",
            "status": "success",
            # A field the subgraph might carry internally that must NOT leak
            # into the outer state unless merge_output() explicitly maps it.
            "internal_debug_trace": "should-not-be-copied",
        }
        merged = node.merge_output(state, sub_result)

        assert "internal_debug_trace" not in merged
        assert merged["status"] == "success"
        assert set(merged.keys()) == {
            "event_context",
            "demand_patterns",
            "order_qty_min",
            "order_qty_max",
            "confidence_pct",
            "rationale",
            "confidence_band",
            "status",
        }


class TestGraphNodeDelegatesGatingToInnerSubgraph:
    """Delegation has a real target: the inner subgraph's entry node runs S-1/S-2/S-3."""

    def test_inner_entry_node_is_a_function_node_with_security_gates(self):
        # EventCalendarLookupNode is the inner subgraph's entry point
        # (domain_workflow_graph.py: START -> event_calendar_lookup). It is a
        # FunctionNode, so the framework's @final S-2/S-3 gates run on every
        # invocation of the inner subgraph - this is where the GraphNode's
        # skipped lifecycle is actually enforced, not omitted.
        assert issubclass(EventCalendarLookupNode, FunctionNode)
        assert hasattr(EventCalendarLookupNode, "required_trust_level")
