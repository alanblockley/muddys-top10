# AgentCore Chart Campaign Requirements

## Purpose

Build an AI-assisted content workflow for Muddy's Top 10 that uses curated chart history to generate weekly DJ readouts, infographic prompts, and social media post drafts.

This document captures the intended direction so future work can continue without relying on chat history.

Detailed planning now lives in [agentic/README.md](agentic/README.md). The
production-agent source specs live in `docs/agent-spec/` and should be treated
as authoritative for generated output style and acceptance criteria.

Implementation baseline: the repo now includes deterministic campaign draft
generation, a scheduled IAM `CampaignGeneratorFunction`, a
`ChartCampaignsTable`, Cognito-protected campaign review APIs, an
IAM-authenticated AgentCore Gateway Lambda target, required AgentCore Memory
for weekly campaign recall, and optional Bedrock-backed JSON generation.
Deterministic generation remains the fallback when no model is configured or
model invocation fails.

Set a custom AgentCore Memory name when needed:

```bash
./deploy.sh --env prod \
  --agentcore-memory-name teleport_prod_agentcore_memory
```

Enable Bedrock-backed campaign generation with:

```bash
./deploy.sh --env prod \
  --campaign-model-id deepseek.v3.2 \
  --campaign-model-endpoint bedrock-mantle
```

## Goals

- Use AgentCore as the agentic platform for AI-facing chart intelligence and content generation.
- Expose task-oriented MCP tools through AgentCore Gateway.
- Avoid routing agent workflows through `MCP -> API Gateway -> Lambda` when direct AgentCore tool backends are more appropriate.
- Preserve the current browser/API Gateway app for human users.
- Reuse the same deterministic chart logic across browser APIs and AgentCore tools.
- Generate weekly content drafts automatically on a schedule.
- Keep human review before publishing.

## Existing Foundations

- Raw track plays are stored in DynamoDB.
- Current Top 10 calculation already applies chart reset configuration and banned-song filters.
- `top10_history` was introduced as an AI-ready weekly chart memory layer.
- Weekly chart snapshots include rank, play count, previous rank, movement, movement delta, chart dates, config, filters, and summary counts.
- `top10_history` avoids forcing agents to recalculate chart history from raw play events.
- `docs/agent-spec/` contains separate production-agent specs for infographic content, social media posts, and radio reads.

## Key Design Principle

Separate deterministic facts from AI-generated language.

Deterministic code should:

- Read chart snapshots.
- Compare the requested chart only with snapshots from earlier weeks.
- Calculate new entries, climbers, drops, returning songs, weeks on chart, best rank, and related chart facts.
- Produce a structured chart brief.

AI should:

- Write DJ readout copy from the structured brief.
- Create infographic render input from the structured brief.
- Create social media post drafts from the structured brief.
- Adapt tone, format, and platform-specific copy.
- Use AgentCore Memory for editorial continuity, reviewer preferences, and avoiding stale repetition.

The model should not infer chart facts directly from raw DynamoDB records.
Memory should not override current chart facts from `chart_brief`.
Campaign generation must not be cognizant of future weeks. A campaign for
`YYYY-MM-DD` can use that week's chart and prior weeks only; later chart
snapshots and later AgentCore Memory records must be excluded.

## Target Architecture

```text
DynamoDB
  tracks
  config
  top10_history
  chart_campaigns

Service layer
  chart history service
  chart brief service
  campaign generation service

Browser API
  API Gateway -> thin Lambda adapter -> service layer

AgentCore
  AgentCore Gateway / MCP tools -> focused Lambda/tool backend -> service layer
  AgentCore Memory -> campaign generation context

Scheduled generation
  EventBridge or AgentCore schedule -> campaign generator -> campaign draft
```

## Service Layer Requirements

Create shared service modules so API Gateway handlers and AgentCore tools use the same business logic.

Suggested modules:

```text
src/services/chart_history.py
src/services/chart_brief.py
src/services/campaign_generation.py
src/services/config_service.py
```

The current monolithic API Lambda can remain initially, but logic should be extracted over time so it becomes a thin HTTP adapter.

## MCP / AgentCore Tool Requirements

Expose capability-oriented tools, not raw HTTP-shaped endpoints.

Initial tool set:

- `get_current_chart()`
- `list_chart_weeks(from_date?, to_date?)`
- `get_chart_week(week_id)`
- `get_chart_range(from_date, to_date)`
- `create_chart_brief(week_id?)`
- `create_dj_readout(week_id?, style?)`
- `create_infographic_prompt_pack(week_id?, platform?)`
- `create_social_post_pack(week_id?, platform?, tone?)`
- `create_chart_campaign(week_id?)`

`create_chart_campaign` should orchestrate the smaller capabilities and return a complete draft package.

The initial content generators should map to the three source specs:

- `create_infographic_content` uses `docs/agent-spec/01a-Infographic-Agent-v3.md`
- final infographic asset generation follows `docs/agent-spec/01b-Generate-Infographic-Asset.md`
- `create_social_posts` uses `docs/agent-spec/02-Social-Agent-v3.md`
- `create_radio_reads` uses `docs/agent-spec/03-Radio-Agent-v3.md`

## Chart Brief Requirements

The chart brief is the core input contract for all AI generation.

It should be structured JSON and include:

- `week_id`
- `chart_date`
- `week_start`
- `week_end`
- `source_snapshot_key`
- `chart_config`
- `filter_patterns`
- ranked tracks
- play counts
- previous rank
- movement
- movement delta
- weeks on chart
- best rank
- last seen week
- new entries
- biggest climbers
- biggest drops
- returning tracks
- notable chart-level summary

Example shape:

```json
{
  "week_id": "2026-07-20",
  "source_snapshot_key": "WEEK#2026-07-20",
  "tracks": [
    {
      "rank": 1,
      "track": "Artist - Title",
      "artist": "Artist",
      "title": "Title",
      "play_count": 42,
      "previous_rank": 3,
      "movement": "up",
      "movement_delta": 2,
      "weeks_on_chart": 4,
      "best_rank": 1,
      "last_seen_week": "2026-07-13"
    }
  ],
  "notables": {
    "new_entries": [],
    "biggest_climbers": [],
    "biggest_drops": [],
    "returning_tracks": []
  }
}
```

## DJ Readout Requirements

Generate per-song DJ readout blocks, not only one long paragraph.

Each entry should include:

- rank
- track
- short intro line
- movement/history line
- DJ readout copy
- outro or transition hook

Example:

```json
{
  "rank": 1,
  "track": "Artist - Title",
  "intro_line": "At number one this week...",
  "movement_line": "Up two places from last week.",
  "readout": "Full DJ-ready copy.",
  "outro_hook": "Keep it locked for more from Muddy's."
}
```

## Infographic Asset Requirements

Generate complete agent-authored HTML/CSS suitable for rendering directly to a
`1280x720` PNG. The agent should use the supplied chart brief and campaign facts
to create the full composition, not fill a static slot template.

The renderer remains responsible for safety and final capture:

- validate canvas size
- block scripts, handlers, remote URLs, external fonts, and external assets
- inject approved local assets such as the Muddy's logo
- render through Playwright/Chromium
- capture the final PNG

The agent-authored package must include:

- `canvas.width = 1280`
- `canvas.height = 720`
- `html`: complete body-level infographic markup
- `css`: complete infographic styles
- `metadata.week_id`
- optional `metadata.design_summary`

The supplied factual context must include:

- week display date
- 10 chart rows
- play counts
- movement type and amount
- notable stories such as #1, biggest climber, new entries, long runners, duplicate artists
- weekly statistics
- chart facts
- Top 10 by the Numbers values
- show and venue text
- warnings or constraints

Example:

```json
{
  "canvas": {
    "width": 1280,
    "height": 720
  },
  "metadata": {
    "week_id": "2026-07-18",
    "design_summary": "Lead with the new number one and biggest climber."
  },
  "html": "<section class=\"poster\">...</section>",
  "css": ".poster { width: 1280px; height: 720px; }"
}
```

Use `{{MUDDYS_LOGO_DATA_URI}}` for the approved dog logo. Do not use remote
images or generated bitmap text.

## Social Post Requirements

Generate multiple platform-specific post drafts.

Include:

- Facebook post
- Instagram caption
- short caption
- hashtags
- call to action
- optional alt text for infographic

Posts must be grounded in the chart brief and must not invent rankings, play counts, or movement.

## Campaign Draft Requirements

Create a new persisted campaign record for generated weekly content.

Recommended table:

```text
ChartCampaignsTable
pk: CAMPAIGN
sk: WEEK#YYYY-MM-DD
```

Recommended attributes:

- `week_id`
- `status`: `draft | reviewed | approved | published`
- `chart_brief`
- `dj_readout`
- `infographic_prompts`
- `social_posts`
- `generated_at`
- `model`
- `prompt_version`
- `source_snapshot_key`
- `reviewed_by`
- `reviewed_at`
- `published_at`

Importantly, generated content should be stored as drafts first.

## Scheduling Requirements

Weekly campaign generation should be automatic.

Recommended flow:

```text
EventBridge schedule
  -> campaign generator
  -> snapshot the countable chart window
  -> build chart brief
  -> generate DJ readout, infographic prompts, and social posts
  -> store campaign draft
  -> notify admin/reviewer
```

Campaign generation is the chart finalization point. The chart then enters a
freeze window until reset: raw plays are retained, but freeze-window plays are
excluded from Top 10 calculations so the Top 10 show play-out does not bias the
next week's chart.

Example default:

- Campaign generation/freeze start: Saturday 02:00 SLT
- Chart reset/new counting window: Saturday 04:00 SLT

Manual regeneration must also be supported:

- regenerate current week
- regenerate a specific `week_id`
- regenerate only one asset type if needed

## Review And Publishing Requirements

Do not auto-publish initially.

Workflow:

```text
draft -> reviewed -> approved -> published
```

Human review should be required before public posting.

The admin/reviewer should be able to:

- inspect source chart facts
- inspect generated DJ copy
- inspect infographic prompts
- inspect social post variants
- regenerate content
- approve content
- mark content as published

## Security And Permissions

AgentCore tools should have least-privilege access by capability.

Suggested separation:

- Read-only chart tools: read `top10_history` and campaign drafts.
- Campaign generation tools: read chart history and write campaign drafts.
- Config/admin tools: read/write config and banned-song filters.
- Spotify tools: isolated access to Spotify secret and playlist generation.
- Data maintenance tools: export/import should remain admin-only and not broadly exposed as agent tools.

Do not give all agent tools the same broad IAM permissions as the current API Lambda.

## Data Source Rules

- Prefer `top10_history` for chart facts.
- Use raw track history only for audits, backfills, or rebuilding chart snapshots.
- Use config table for chart generation settings and banned-song filters.
- Generated copy must include provenance: `week_id` and `source_snapshot_key`.

## Phased Implementation Plan

### Phase 1: Deterministic Chart Brief

- Extract chart history access into a service module.
- Implement `create_chart_brief(week_id?)`.
- Include historical comparisons, notables, weeks-on-chart, and best-rank calculations.
- Add tests for brief generation using fixture chart snapshots.

### Phase 2: Manual Campaign Generation

- Implement `create_chart_campaign(week_id?)`.
- Generate DJ readout, infographic render input, and social posts.
- Store campaign drafts in `ChartCampaignsTable`.
- Add manual invocation path through CLI or admin-only tool.

### Phase 3: AgentCore / MCP Tools

- Add AgentCore Gateway-facing tools over the service layer.
- Do not route tools through API Gateway.
- Keep tool outputs structured and agent-friendly.

### Phase 4: Scheduled Weekly Drafts

- Add EventBridge or AgentCore schedule.
- Generate campaign draft after chart snapshot finalization.
- Notify admin/reviewer.

### Phase 5: Review UI

- Add admin UI to review and regenerate campaign drafts.
- Add approval and published status tracking.

### Phase 6: Publishing Integrations

- Optional future work.
- Add platform-specific publishing only after review workflow is proven.

## Open Questions

- Which model/provider should generate campaign content?
- Should generated content be stored in DynamoDB only, or also exported to S3 as JSON artifacts?
- What notification channel should be used for draft review?
- What brand voice should the DJ readout use?
- Which infographic platforms/aspect ratios are required first?
- Should generated campaign drafts include rendered infographic asset metadata before publishing, or should rendering remain a separate approval action initially?
