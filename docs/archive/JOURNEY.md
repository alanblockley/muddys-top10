# Agentic Journey

## Goal

Create a weekly, reviewable content workflow that turns Muddy's Top 10 chart
facts into approved campaign assets:

- broadcast-ready radio reads
- channel-specific social copy
- a branded `1280x720` infographic PNG
- source/reference data for audit
- revision history for refinement
- feedback data for future prompt improvement

## End-To-End Flow

```text
Weekly chart snapshot
  -> deterministic chart brief
  -> system branding config
  -> selected infographic template
  -> campaign context pack
  -> AgentCore Runtime
  -> Strands creative agents
  -> generated campaign revision
  -> validation
  -> PNG render
  -> human review
  -> feedback / refinement / approval
  -> published marker or export
```

## Actions Vs AWS Components

User/admin actions:

- generate campaign
- view campaign
- refine campaign revision
- rate asset up/down
- approve revision
- publish/export
- manage branding settings
- manage template versions
- trigger prompt optimisation

AWS/application components:

- CloudFront admin UI for human interaction.
- API Gateway and API Lambda for Cognito-protected admin actions.
- Campaign Generator Lambda for scheduled generation.
- AgentCore Runtime for campaign workflow execution.
- AgentCore Gateway for IAM-authenticated tool access.
- AgentCore Memory for creative continuity and feedback-derived preferences.
- AgentCore Tools Lambda for chart/history/campaign/rendering tools.
- DynamoDB for chart history, config, campaigns, revisions, feedback, and
  template metadata.
- S3 for rendered PNGs and versioned template source assets.
- Bedrock Prompt Management for versioned prompt templates.
- Bedrock/Mantle model access for creative generation.
- EventBridge Scheduler for weekly automatic campaign creation.

## System Roles

### Deterministic Services

Deterministic services are responsible for facts and repeatable calculations:

- read `top10_history`
- select the requested chart week
- enforce temporal boundaries
- compare with earlier weeks only
- calculate chart notables
- prepare the `chart_brief`
- resolve branding/template/prompt versions
- validate generated HTML/CSS and campaign structures
- persist campaigns, revisions, feedback, and statuses

### AgentCore Runtime

AgentCore Runtime is the agentic execution boundary. Browser/API and scheduled
workloads invoke the runtime. The runtime should own the campaign workflow and
delegate creative stages to Strands agents.

### Strands Creative Agents

Planned agents:

- `CampaignPlannerAgent`
- `RadioReadAgent`
- `SocialCopyAgent`
- `InfographicDesignAgent`
- `FeedbackSummarizerAgent`

These agents transform authoritative facts into creative campaign assets. They
must not invent chart facts.

### AgentCore / MCP Tools

AgentCore-facing tools expose task-oriented capabilities, not raw API Gateway
wrappers.

Initial/current tools:

- `get_current_chart`
- `list_chart_weeks`
- `get_chart_week`
- `get_chart_range`
- `create_chart_brief`
- `create_radio_reads`
- `create_infographic_content`
- `create_social_posts`
- `create_chart_campaign`
- `get_chart_campaign`
- `list_chart_campaigns`
- `update_chart_campaign_status`

Planned tools:

- `get_campaign_revision`
- `save_campaign_revision`
- `list_infographic_templates`
- `get_infographic_template`
- `render_infographic_png`
- `save_asset_feedback`
- `summarize_feedback_to_memory`
- `get_prompt_version`

### AgentCore Memory

AgentCore Memory is the creative recall layer. It stores summaries of prior
campaigns, visual decisions, reviewer preferences, and repeated issues.

Memory should remember:

- phrases to avoid repeating
- previously rejected visual styles
- successful design choices
- user tone preferences
- recurring feedback themes

Memory should not remember or override:

- chart rank
- play count
- movement
- weeks on chart
- current week facts

## Boundary Decisions

- Do not route AgentCore tools through `MCP -> API Gateway -> Lambda` unless
  there is no better option.
- Keep the browser/API Gateway stack for human UI access.
- Keep facts deterministic and auditable.
- Use Strands for creative stages, not for factual calculation.
- Treat logo, chart title, and tag line as non-negotiable.
- Treat colour scheme and font as bounded design tokens.
- Use versioned templates as creative input, not as mutable final output.
- Store campaign-generated HTML/CSS and PNGs immutably by revision.
- Prompt optimisation creates candidates only; admin promotion is required.

## Weekly Schedule

The real-world show flow is:

```text
Saturday 02:00 SLT
  -> campaign generation / chart freeze begins

Saturday 04:00 SLT
  -> chart reset / next chart starts counting
```

Raw plays are still retained during the freeze window. Top 10 aggregation
excludes frozen plays to avoid Top 10 show play-out bias.

## Human Review

The agentic system should make publishing faster, not remove editorial control.

Primary review order:

1. Infographic PNG with download link.
2. Social copy tabs for Facebook, Primfeed, and Discord.
3. DJ on-air reads per track.
4. Source/reference chart data.
5. Full JSON/debug detail.

Review actions:

- rate an asset up/down with optional free-text feedback
- request a refined revision
- regenerate one section
- approve a revision
- mark as published

Old revisions remain available for audit.
