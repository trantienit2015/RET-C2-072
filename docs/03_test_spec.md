# Test Specification

## Test Strategy
- Coverage target: every node ≥1 unit success + ≥1 error/edge; full graph ≥1 integration compile+invoke.
- Test types: Unit (`tests/unit/`) / Integration (`tests/integration/`) / Proof-of-Boundary (`tests/proof_of_boundary/`)

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | Fail-closed validation on invalid input | Empty/invalid input → `AgentStatus.ERROR`, no raise | PASS |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations | PASS |
| TC-04 | InvocationContext via configurable only | Direct access raises error | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start` / `node_complete` / `node_error` absent from `execute()` body | 0 duplicates |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | 0 overrides |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | 0 overrides |
| TC-08 | `required_trust_level` declared + enforced | Insufficient trust → refused; all values valid enum | PASS |
| TC-09 | S-2: `_extra_security_gate_input()` | Not implemented — default PII scan on `user_input`/`validated_input` sufficient | N/A |
| TC-10 | S-3: `_extra_security_gate_output()` non-suppressible re-check | `HITLDisclaimerGateNode` blocks suppressed disclaimer with ERROR dict (never raises) | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` (incl. GraphNode `extract_input`/`merge_output` hooks) | Domain event emitted on every invocation path | ≥1 per node |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | PASS |
| PB-3 | L1 → External service | Demand-summary KB + event-calendar KB lookup via injected config | Data retrieved | PASS (fake KB in tests) |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete` | Order verified | PASS |
| PB-7 | HITL interrupt propagation | `hitl.enabled` is `false` for this template (no D6 `interrupt()`) — stub auto-skips | Skip (N/A) | SKIP |

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Full graph happy path | NL order-guidance question + populated demand/event KB | `status=SUCCESS`, `final_guidance` contains confidence band + JP disclaimer | PASS |
| BL-02 | Empty demand KB | NL question, empty `demand_kb` | `status=ERROR` (no fabricated recommendation) | PASS |
| BL-03 | HITL disclaimer non-suppression | `final_guidance` missing disclaimer text (simulated) | `_extra_security_gate_output` returns `status=ERROR` | PASS |

## Test Execution Summary
- Execution date: 2026-07-11
- Total tests: see `pytest tests/ -v` output in MR pipeline
- Pass / Fail / Skip: see CI pipeline (PB-7 SKIP expected — `hitl.enabled: false`)
- Coverage: all 6 nodes + outer/inner graph covered by unit + integration tests
