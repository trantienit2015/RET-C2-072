# RET-C2-072 - Unit tests: per-node success + error/edge paths.

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.confidence_band_format_node import ConfidenceBandFormatNode
from src.nodes.demand_history_retrieve_node import DemandHistoryRetrieveNode
from src.nodes.event_calendar_lookup_node import EventCalendarLookupNode
from src.nodes.hitl_disclaimer_gate_node import DISCLAIMER_JA, HITLDisclaimerGateNode
from src.nodes.input_normalize_node import InputNormalizeNode
from src.nodes.order_guidance_generate_node import OrderGuidanceGenerateNode

DEMAND_KB = [
    {"date": "2026-07-01", "qty": 90},
    {"date": "2026-07-02", "qty": 100},
    {"date": "2026-07-03", "qty": 110},
]
EVENT_KB = [
    {"name": "school holiday", "within_days": 5},
    {"name": "summer festival", "within_days": 30},
]


class TestInputNormalizeNode:
    def test_success(self):
        state = {"user_input": "How much should I order for tomorrow's lunch slot?"}
        r = InputNormalizeNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["normalized_intent"]
        payload = json.loads(r["validated_input"])
        assert payload["query_window_days"] == 7

    def test_empty_input_error(self):
        assert InputNormalizeNode().execute({"user_input": ""})["status"] == AgentStatus.ERROR

    def test_trust_gate_enforced(self):
        node = InputNormalizeNode()
        state = {
            "user_input": "order guidance please",
            "caller_trust_level": TrustLevel.ANONYMOUS.value,
            "correlation_id": "trust-test-1",
        }
        result = node(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert any("S-1 trust gate denied" in e for e in result.get("error_log", []))


class TestEventCalendarLookupNode:
    def test_success(self):
        state = {"user_input": json.dumps({"query": "order?", "query_window_days": 7})}
        r = EventCalendarLookupNode(event_kb=EVENT_KB).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert "school holiday" in r["event_context"]
        assert "summer festival" not in r["event_context"]

    def test_no_events_within_window(self):
        state = {"user_input": json.dumps({"query": "order?", "query_window_days": 1})}
        r = EventCalendarLookupNode(event_kb=EVENT_KB).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["event_context"] == []

    def test_empty_kb(self):
        state = {"user_input": json.dumps({"query": "order?", "query_window_days": 7})}
        r = EventCalendarLookupNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["event_context"] == []


class TestDemandHistoryRetrieveNode:
    def test_success(self):
        state = {"user_input": json.dumps({"query": "order?", "query_window_days": 7})}
        r = DemandHistoryRetrieveNode(demand_kb=DEMAND_KB, top_k=2).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert len(r["demand_patterns"]) == 2

    def test_empty_kb_error(self):
        state = {"user_input": json.dumps({"query": "order?", "query_window_days": 7})}
        r = DemandHistoryRetrieveNode(demand_kb=[]).execute(state)
        assert r["status"] == AgentStatus.ERROR

    def test_invalid_input_error(self):
        r = DemandHistoryRetrieveNode(demand_kb=DEMAND_KB).execute({"user_input": ""})
        assert r["status"] == AgentStatus.ERROR


class TestOrderGuidanceGenerateNode:
    def test_success(self):
        state = {"demand_patterns": DEMAND_KB, "event_context": ["school holiday"]}
        r = OrderGuidanceGenerateNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["order_qty_min"] <= r["order_qty_max"]
        assert r["rationale"]

    def test_uses_injected_llm(self):
        class FakeLLM:
            def complete(self, messages) -> str:
                return "fake rationale"

        state = {"demand_patterns": DEMAND_KB, "event_context": []}
        r = OrderGuidanceGenerateNode(llm=FakeLLM()).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["rationale"] == "fake rationale"

    def test_uses_injected_llm_canonical_dict_response(self):
        class DictLLM:
            def complete(self, messages) -> dict:
                return {"content": "dict rationale", "tool_calls": [], "model": "fake", "usage": {}}

        state = {"demand_patterns": DEMAND_KB, "event_context": []}
        r = OrderGuidanceGenerateNode(llm=DictLLM()).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["rationale"] == "dict rationale"
        assert isinstance(r["rationale"], str)

    def test_llm_raises_is_error_not_swallowed(self):
        class RaisingLLM:
            def complete(self, messages):
                raise TimeoutError("provider timeout")

        state = {"demand_patterns": DEMAND_KB, "event_context": []}
        r = OrderGuidanceGenerateNode(llm=RaisingLLM()).execute(state)
        assert r["status"] == AgentStatus.ERROR

    def test_llm_empty_response_is_error_not_swallowed(self):
        class EmptyLLM:
            def complete(self, messages) -> dict:
                return {"content": ""}

        state = {"demand_patterns": DEMAND_KB, "event_context": []}
        r = OrderGuidanceGenerateNode(llm=EmptyLLM()).execute(state)
        assert r["status"] == AgentStatus.ERROR

    def test_no_demand_patterns_error(self):
        r = OrderGuidanceGenerateNode().execute({"demand_patterns": []})
        assert r["status"] == AgentStatus.ERROR


class TestConfidenceBandFormatNode:
    def test_success(self):
        state = {"order_qty_min": 85, "order_qty_max": 95}
        r = ConfidenceBandFormatNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert "85" in r["confidence_band"] and "95" in r["confidence_band"]

    def test_missing_band_error(self):
        r = ConfidenceBandFormatNode().execute({})
        assert r["status"] == AgentStatus.ERROR


class TestHITLDisclaimerGateNode:
    def test_success(self):
        state = {"rationale": "recommend 85-95 units", "confidence_band": "85-95 units, 80% confidence"}
        r = HITLDisclaimerGateNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert DISCLAIMER_JA in r["final_guidance"]
        assert r["disclaimer_text"] == DISCLAIMER_JA

    def test_missing_confidence_band_error(self):
        r = HITLDisclaimerGateNode().execute({"rationale": "x"})
        assert r["status"] == AgentStatus.ERROR

    def test_extra_gate_blocks_suppressed_disclaimer(self):
        bad_state = {"final_guidance": "recommendation without disclaimer"}
        out = HITLDisclaimerGateNode()._extra_security_gate_output(bad_state)
        assert out["status"] == AgentStatus.ERROR
        assert any("suppressed" in e.lower() for e in out.get("error_log", []))

    def test_extra_gate_passthrough_valid_output(self):
        good_state = {"final_guidance": f"rationale\n\nband\n\n{DISCLAIMER_JA}"}
        out = HITLDisclaimerGateNode()._extra_security_gate_output(good_state)
        assert out is good_state


class TestResolveTopK:
    def test_bounds_and_fallback(self):
        from src.services.service import DEFAULT_TOP_K, MAX_TOP_K, resolve_top_k

        assert resolve_top_k(3) == 3
        assert resolve_top_k("4") == 4
        assert resolve_top_k(MAX_TOP_K + 1) == MAX_TOP_K
        for bad in (0, -1, None, "x", True, 2.5):
            assert resolve_top_k(bad) == DEFAULT_TOP_K

    def test_node_clamps_top_k(self):
        kb = [{"date": f"2026-07-{d:02d}", "qty": d} for d in range(1, 29)]
        state = {"user_input": json.dumps({"query": "order?", "query_window_days": 7})}
        r = DemandHistoryRetrieveNode(demand_kb=kb * 3, top_k=10_000).execute(state)
        assert len(r["demand_patterns"]) == 50
