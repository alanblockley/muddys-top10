# Agentic Workflow Planning

This folder defines the planned agentic publishing workflow for Muddy's Top 10.
It is planning documentation only; current implementation remains documented in
the root `README.md` and the current-system docs.

## Source Agent Specs

The specific production-agent instructions live in `docs/agent-spec/` and are
authoritative for output style and acceptance criteria:

- [Infographic Editorial Agent](../agent-spec/01a-Infographic-Agent-v3.md)
- [Infographic Asset Renderer](../agent-spec/01b-Generate-Infographic-Asset.md)
- [Social Media Agent](../agent-spec/02-Social-Agent-v3.md)
- [Radio Reads Agent](../agent-spec/03-Radio-Agent-v3.md)

Do not duplicate those specs into implementation prompts by hand. Load or render
them as reusable context so updates to `docs/agent-spec/` remain effective.

## Planning Docs

- [JOURNEY.md](JOURNEY.md) - End-to-end agentic journey and workflow boundaries.
- [CONTEXT_PACKS.md](CONTEXT_PACKS.md) - Context files, personal voice inputs, and precedence rules.
- [OUTPUT_CONTRACTS.md](OUTPUT_CONTRACTS.md) - Structured data contracts for agent inputs and outputs.
- [REVIEW_WORKFLOW.md](REVIEW_WORKFLOW.md) - Draft, review, approval, and publishing lifecycle.
- [ROADMAP.md](ROADMAP.md) - Practical implementation phases.
- [AGENT_HANDOFF.md](AGENT_HANDOFF.md) - Condensed handoff for future agents if context is lost.

## Core Principle

Deterministic code owns chart facts. Agents own editorial transformation.

The model must not infer rankings, movement, play counts, weeks on chart, or
historical claims from raw data. Those facts must come from a generated
`chart_brief` derived from `top10_history`.
