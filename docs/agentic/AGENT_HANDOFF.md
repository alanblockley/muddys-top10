# Agent Handoff: Agentic Campaign Plan

This file is the short-form context handoff for future agents. Use it when the
conversation context is lost or work is interrupted.

## Current Intent

Build Muddy's Top 10 into an AgentCore-led weekly campaign system that produces:

- immutable infographic PNG assets
- social copy for Facebook, Primfeed, and Discord
- DJ on-air reads per chart entry
- campaign revision history
- feedback-driven improvement over time

The workflow must be reliable and auditable, while the creative outputs should
be less static and less repetitive week to week.

## Non-Negotiable Decisions

- AgentCore is required, not optional.
- Scheduled campaign generation runs outside user scope with IAM, not Cognito.
- Chart facts come from deterministic `top10_history`/`chart_brief`, not memory
  or model inference.
- Historical campaigns must not use future chart weeks or future memory.
- Logo, chart title, and tag line are system-level brand non-negotiables.
- Colour scheme and font are bounded design tokens.
- Campaign assets are immutable once generated.
- Refinement creates a new revision; it does not mutate approved assets.
- Prompt optimisation must not auto-promote. Admin approval is required.

## Current Implementation Baseline

The repo currently has:

- Cognito-protected admin UI and APIs.
- AgentCore Runtime invocation for campaign generation.
- AgentCore Gateway and Lambda-backed tools.
- AgentCore Memory integration for editorial continuity.
- DynamoDB campaign draft storage.
- S3 campaign asset storage.
- Server-side infographic PNG rendering.
- Admin campaign management UI.
- System-level campaign branding selectors.
- Initial versioned infographic template config with one built-in template.
- Backward-compatible `CAMPAIGN_REVISION` writes for completed generations.
- Revision list/detail APIs and modal revision visibility.
- Revision approval by id promotes the chosen revision as the active approved
  campaign snapshot.
- Revision comparison UI shows two revisions side by side for infographic,
  social, and radio-read review.
- Infographic asset validation runs before rendering and is shown in campaign
  and revision review.
- Model-authored infographic HTML/CSS generation exists with validation and
  template fallback.
- AgentCore Runtime now uses Strands Agent/tool routing while preserving the
  existing runtime action contract.
- Campaign branding supports raster logo upload to the campaign assets bucket;
  generated PNGs use the uploaded logo key captured in the brand snapshot, with
  the bundled logo as fallback.
- Optional Bedrock Prompt Management references exist for `radio_reads`,
  `infographic`, `social`, and `infographic_asset`; blank or failed references
  fall back to built-in prompts.
- Campaign review feedback capture exists for infographic, social copy, and
  radio reads, stored against immutable campaign revisions.
- Campaign feedback summary exists in the Campaigns admin tab and through
  `/api/campaigns/feedback/summary`; it uses campaigns table `gsi1` on
  `gsi_pk = FEEDBACK_SUMMARY`.
- Current model default: `deepseek.v3.2` via `bedrock-mantle`.

Known limitation:

- Runtime orchestration is still thin and mostly coded.
- Infographic HTML/CSS is still too template/static because layout assembly is
  currently Python-driven.

## Target Architecture

```text
API/UI or schedule
  -> AgentCore Runtime
  -> deterministic workflow controller
  -> Strands creative agents
  -> AgentCore tools
  -> Bedrock Prompt Management
  -> AgentCore Memory
  -> versioned infographic template input
  -> generated campaign revision
  -> validation
  -> renderer Lambda
  -> immutable PNG in S3
  -> campaign/revision metadata in DynamoDB
```

## Next Major Work

Do not start with Strands until the data contracts it needs are stable.

Recommended order:

1. Expand the template store with S3-backed upload/version admin flows.
2. Expand Strands from runtime routing into stage-specific creative agents.
3. Seed initial Bedrock Prompt Management assets and switch config from blank
   built-in prompts to explicit managed prompt versions.
4. Add feedback memory summarisation.
5. Add manual prompt optimisation and A/B promotion.
6. Add refinement chat against campaign revisions.

## Prompt Management Baseline

System config key:

```json
{
  "campaign_prompts": {
    "radio_reads": {
      "prompt_identifier": "",
      "prompt_version": "",
      "variant_name": ""
    },
    "infographic": {
      "prompt_identifier": "",
      "prompt_version": "",
      "variant_name": ""
    },
    "social": {
      "prompt_identifier": "",
      "prompt_version": "",
      "variant_name": ""
    },
    "infographic_asset": {
      "prompt_identifier": "",
      "prompt_version": "",
      "variant_name": ""
    }
  }
}
```

Runtime behaviour:

- `AgentCoreToolsFunction` reads config and calls Bedrock Prompt Management
  `GetPrompt` only when a prompt identifier is configured.
- Prompt templates use local `{{variable}}` replacement before model invocation.
- Campaign generator metadata records `prompt_refs` for each generated section.
- Fetch/render failures use the built-in prompt and record `fallback_reason`.

## Template Store Requirement

The infographic layout should be stored as a versioned asset:

```text
DynamoDB metadata:
  template_id
  version
  status
  s3_html_key
  s3_css_key
  preview_png_key

S3 assets:
  templates/{template_id}/{version}/template.html
  templates/{template_id}/{version}/template.css
  templates/{template_id}/{version}/preview.png
```

The template is an input to the agent, not the final output.

## Validation Requirement

Generated infographic HTML/CSS must be validated before render/save:

- exact chart title present
- exact tag line present
- logo placeholder present
- all 10 ranks present
- artist/title/movement/play fields represented
- no external scripts
- no external network assets
- `1280x720` canvas
- approved palette/font tokens used

## Rollback Guidance

Keep implementation changes narrow and revertable:

- template store in one change
- revision model in one change
- agent-authored HTML/CSS in one change
- Strands migration in one change
- Prompt Management in one change

Avoid combining schema changes, runtime migration, and UI overhaul in the same
commit.
