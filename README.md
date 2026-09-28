# RET-C2-072 — Retail Demand Forecast Q&A & Replenishment Guidance Agent

> **Category**: Cat 2 (orchestrates multiple steps to accomplish a specific use case)
> **Industry**: RET

## Overview

A store manager or franchise owner asks a natural-language order question, for example
"How many units should I order for next week?". The agent answers with a recommended order
quantity band, a short rationale, and a fixed disclaimer (in Japanese) reminding the user
that the final order decision is theirs.

How it works today:

- **Input normalisation** (outer `pre_process`): rejects an empty question and wraps the
  question into a JSON envelope with a fixed 7-day look-ahead window.
- **Inner workflow** (a `GraphNode` in the `main` slot) runs four steps:
  1. look up events from an injected event-calendar list (`event_kb`) that fall within the window;
  2. take the most recent demand-history records (`demand_kb`, sorted by date, up to 8);
  3. compute an order band of ±10 % around the average recent quantity. When no LLM client
     is configured the rationale is a deterministic template sentence; when one is
     configured, the LLM writes the rationale (the quantity band is always computed
     deterministically);
  4. format the band with a **fixed 80 % confidence label** — this value is a constant, not a
     statistical estimate.
- **Disclaimer gate** (outer `post_process`): appends the disclaimer and, as an output-gate
  re-check, returns an error if the disclaimer is missing from the result.

The demand-history and event-calendar data are not bundled. They are passed in through the
graph config (`demand_kb`, `event_kb`); with no demand data the agent returns an explicit
error instead of inventing a number. The standalone HTTP entry point (`src/api/server.py`)
falls back to a small built-in sample dataset when the config supplies none, so a local
smoke run can complete — that sample is not real demand data. No external API or database
is called; the only optional external dependency is an LLM client for the rationale text.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | 3.11 or later |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and test specification
```

See `docs/02_design.md` for the design and `docs/03_test_spec.md` for the test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
