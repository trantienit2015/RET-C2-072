# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `Graph` (outer) — `src.graph.graph.Graph`
- **L1 Base**: `AgentBaseGraph` (L1 direct)
- **Cat 2 pattern**: outer `AgentBaseGraph` backbone + `GraphNode` (`OrderGuidanceGraphNode`,
  same file `src/graph/graph.py`) in the `main` slot, wrapping an inner `BaseGraph`
  (`OrderGuidanceWorkflowGraph`, `src/graph/domain_workflow_graph.py`).
- **Three-Layer Separation**:
  - State: flat TypedDict composition (`src/schemas/state.py`, no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

### Node Configuration

**Outer graph** (`src/graph/graph.py`, `AgentBaseGraph`):

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | — | — | InitializeNode (default) |
| pre_process | `InputNormalizeNode` — parse NL order-guidance question, S-2 input scan, serialize `validated_input` JSON envelope for the inner subgraph | `user_input` | `normalized_intent`, `query_window_days`, `validated_input` | FunctionNode |
| main | `OrderGuidanceGraphNode` — dispatches to inner `OrderGuidanceWorkflowGraph` (event lookup → demand retrieve → guidance generate → confidence band) | `validated_input` | `event_context`, `demand_patterns`, `order_qty_min/max`, `confidence_pct`, `rationale`, `confidence_band` | GraphNode |
| post_process | `HITLDisclaimerGateNode` — assembles final guidance + attaches non-suppressible HITL disclaimer (S-3 re-check) | `rationale`, `confidence_band` | `disclaimer_text`, `final_guidance`, `formatted_output` | FunctionNode |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

**Inner subgraph** (`src/graph/domain_workflow_graph.py`, `OrderGuidanceWorkflowGraph` — `BaseGraph`):

| Node | Responsibility | Input | Output |
|------|---------------|-------|--------|
| `event_calendar_lookup` | `EventCalendarLookupNode` — event-calendar KB lookup within query window | `user_input` (JSON: query + window) | `event_context` |
| `demand_history_retrieve` | `DemandHistoryRetrieveNode` — deterministic recency-window lookup over the demand-summary KB (most-recent-first date sort, `top_k` from `config/config.yaml`, passed outer graph → `OrderGuidanceGraphNode` → inner subgraph → node; bounded to 1..50, invalid/absent → 8; no semantic/keyword ranking) | inner `user_input` | `demand_patterns` |
| `order_guidance_generate` | `OrderGuidanceGenerateNode` — LLM order quantity + rationale grounded on demand + event context | `demand_patterns`, `event_context` | `order_qty_min/max`, `rationale` |
| `confidence_band_format` | `ConfidenceBandFormatNode` — formats confidence band string | `order_qty_min/max` | `confidence_band`, `confidence_pct` |

### Data Flow

```
START → initialize → pre_process (InputNormalize)
                          → main (OrderGuidanceGraphNode)
                                → [inner: event_calendar_lookup → demand_history_retrieve
                                          → order_guidance_generate → confidence_band_format]
                          → post_process (HITLDisclaimerGate) → finalize → END
                                            ↓ (retry)
                                          pre_process
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `normalized_intent` | `NotRequired[str]` | parsed NL question | pre_process |
| `query_window_days` | `NotRequired[int]` | lookahead window for event/demand lookup | pre_process |
| `event_context` | `NotRequired[list[str]]` | event-calendar hits | inner → merge_output |
| `demand_patterns` | `NotRequired[list[dict]]` | demand-history retrieval results | inner → merge_output |
| `order_qty_min` / `order_qty_max` | `NotRequired[int]` | recommended order-quantity band | inner → merge_output |
| `confidence_pct` | `NotRequired[int]` | confidence percentage | inner → merge_output |
| `rationale` | `NotRequired[str]` | LLM-grounded rationale | inner → merge_output |
| `confidence_band` | `NotRequired[str]` | formatted band string | inner → merge_output |
| `disclaimer_text` | `NotRequired[str]` | non-suppressible HITL disclaimer text | post_process |
| `final_guidance` | `NotRequired[str]` | assembled final answer | post_process |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types); every agent-specific field wraps `NotRequired[...]`.
- No JWT, API keys, credentials in State (checkpoint DB leakage).
- InvocationContext via `config["configurable"]` only (not in State).
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible).

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [ ] ConnectionPolicy (retry/timeout strategy)
- [ ] SecurityViolationError
- [ ] S-2: `_extra_security_gate_input()` — not implemented; default PII scan on `user_input`/`validated_input` is sufficient for this template.
- [x] S-3: `_extra_security_gate_output()` — `HITLDisclaimerGateNode` implements a **non-suppressible re-check**:
      verifies the JP disclaimer string is present in the node's own `final_guidance` output; returns an ERROR
      dict (never raises) if suppressed. This is the "preservation variant" of S-3 (verify safety-critical
      content is retained), not a filtering gate.
- [x] S-4: `emit_trace_event()` — every node (outer `InputNormalizeNode`/`HITLDisclaimerGateNode`, inner 4 nodes,
      `GraphNode` dispatch/completion hooks) emits ≥1 domain event; never re-emits `node_start`/`node_complete`/`node_error`.

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied)
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation)

### Composition Pattern

- **Pattern**: `GraphNode` (subgraph) — Cat 2, `main` slot wraps `OrderGuidanceWorkflowGraph`.
- **Composition target**: `src/graph/domain_workflow_graph.py::OrderGuidanceWorkflowGraph`.
- **Error propagation strategy**: `propagate` (fail-fast — inner subgraph error surfaces as `SubgraphError`, `error_strategy="propagate"` on `OrderGuidanceGraphNode`).

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed multi-step advisory pipeline, no autonomous termination logic needed. |
| Composition pattern | Flat Cat 1 (single MainNode) | GraphNode + inner subgraph (Cat 2) | **GraphNode + inner subgraph** | Cat 2 requires `main` slot wrapped by `GraphNode`; 4 domain steps live in the inner workflow (`gate-composition`). |
| HITL disclaimer mechanism | D6 `interrupt()` (pause/resume) | Deterministic non-suppressible assertion node + S-3 re-check | **Deterministic assertion** | The disclaimer is always attached and never removable by config — no human review/approval loop is needed (the agent only advises; it never places the order), so D6 interrupt/resume is unnecessary. `hitl.enabled` stays `false`. |

## Dependencies (operator-managed, PM/customer-scope)

- Demand-summary KB (rolling 90-day+ window) — injected via entry-point config (`demand_kb` list of
  `{date, qty, ...}` records), operator-managed and versioned.
- Event-calendar KB — injected similarly (`event_kb` list of `{name, within_days}` records), operator-managed.
- Neither KB is a hard blocker for Phase 3 build — the pipeline
  returns an explicit ERROR status when a KB has no matching data, rather than fabricating a recommendation.
