"""AgentCore Platform v1.0"""

# Service layer: domain queries, external API wrappers, data aggregation.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.
#
# Demand-summary KB and event-calendar KB are operator-managed inputs
# (docs/02_design.md §Dependencies). This module provides pure lookup
# helpers over the injected KB payloads — no side effects, no I/O.

from __future__ import annotations

from typing import Any


def lookup_event_calendar(event_kb: list[dict[str, Any]], window_days: int) -> list[str]:
    """Return event names within the given lookahead window (days)."""
    if not event_kb:
        return []
    return [
        e.get("name", "")
        for e in event_kb
        if isinstance(e, dict) and e.get("within_days", 9999) <= window_days and e.get("name")
    ]


DEFAULT_TOP_K = 8
MAX_TOP_K = 50


def resolve_top_k(value: Any) -> int:
    """Bound the config ``top_k`` to 1..MAX_TOP_K; non-integer or < 1 falls back to DEFAULT_TOP_K."""
    if isinstance(value, bool):
        return DEFAULT_TOP_K
    try:
        k = int(value)
    except (TypeError, ValueError):
        return DEFAULT_TOP_K
    if isinstance(value, float) and value != k:
        return DEFAULT_TOP_K
    if k < 1:
        return DEFAULT_TOP_K
    return min(k, MAX_TOP_K)


def retrieve_demand_patterns(demand_kb: list[dict[str, Any]], top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    """Deterministic recency-window lookup: most-recent-first over the demand-summary KB."""
    if not demand_kb:
        return []
    ranked = sorted(demand_kb, key=lambda r: r.get("date", ""), reverse=True)
    return ranked[: resolve_top_k(top_k)]


def estimate_order_band(patterns: list[dict[str, Any]]) -> tuple[int, int]:
    """Derive a +/-10% order-quantity band from recent demand quantities."""
    qty_values = [q for q in (p.get("qty") for p in patterns) if isinstance(q, (int, float))]
    if not qty_values:
        return 0, 0
    avg = sum(qty_values) / len(qty_values)
    qty_min = max(int(round(avg * 0.9)), 0)
    qty_max = max(int(round(avg * 1.1)), qty_min + 1)
    return qty_min, qty_max
