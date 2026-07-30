# Agentic Implementation Roadmap

This roadmap is the working plan for the Muddy's Top 10 agentic campaign
system. It separates stable deterministic services from creative agent work so
campaigns can become more expressive without losing factual control,
immutability, or reviewability.

## Current Baseline

Implemented baseline:

- Cognito-protected admin campaign APIs.
- AgentCore Runtime as the campaign execution boundary.
- AgentCore Gateway and Lambda-backed chart/campaign tools.
- AgentCore Memory for editorial continuity.
- Weekly scheduled campaign generation with chart freeze support.
- DynamoDB campaign draft storage.
- S3-backed rendered campaign PNG assets.
- Admin campaign list/detail/review/status/delete UI.
- Server-side HTML/CSS to PNG rendering.
- System-level campaign branding controls for uploaded logo, free-text chart
  title/tagline, colour scheme, and font.
- Optional Bedrock Prompt Management references for campaign generation
  prompts, with built-in code prompts as fallback.

Known architectural gap:

- The current AgentCore runtime is thin and delegates to coded orchestration.
- The current infographic layout is still too rigid because the stored asset is
  assembled by Python rather than authored by a creative agent from a versioned
  layout template.

## Target Architecture

```text
Chart history / config
  -> deterministic chart brief builder
  -> campaign context assembler
  -> AgentCore Runtime
  -> deterministic workflow controller
  -> Strands creative agents
  -> Bedrock Prompt Management prompts
  -> AgentCore Memory for creative continuity
  -> validated campaign revision
  -> renderer Lambda
  -> immutable PNG in S3
  -> campaign/revision metadata in DynamoDB
  -> human review / feedback / approval
```

Deterministic code owns:

- chart facts
- temporal boundaries
- prompt/template/version lookup
- validation
- rendering
- persistence
- approval state

Agents own:

- creative strategy
- radio read wording
- social copy
- infographic layout adaptation
- visual variation within brand constraints
- feedback summarisation

## Phase 1: System Branding Config

Status: initial implementation exists.

Purpose: define static non-negotiable campaign branding once at system level.

System settings:

- uploaded logo image
- free-text chart title
- free-text tag line
- colour scheme
- font style

Rules:

- Logo, chart title, and tag line are hard constraints.
- Colour scheme and font are creative design tokens, not free-form choices.
- New campaigns receive a snapshot of the resolved branding config.
- Existing campaign assets do not change when branding settings change.
- Uploaded logos are stored in the campaign assets bucket and new PNG renders
  use the logo key captured in the campaign brand snapshot.

Remaining work:

- Record the resolved brand snapshot explicitly on each campaign revision.
- Add tests that the generated HTML includes exact title/tagline/logo
  placeholder.

## Phase 2: Versioned Infographic Template Store

Status: initial implementation exists.

Purpose: replace hard-coded Python layout assembly with stored, versioned
template assets that the infographic agent uses as creative input.

Storage model:

```text
DynamoDB template metadata
  template_id
  version
  name
  description
  status: draft | active | retired
  created_at
  created_by
  s3_html_key
  s3_css_key
  preview_png_key
```

```text
S3 template assets
  templates/{template_id}/{version}/template.html
  templates/{template_id}/{version}/template.css
  templates/{template_id}/{version}/preview.png
```

Rules:

- The template is input, not the final output.
- The agent may adapt layout details, spacing, emphasis, and hierarchy.
- The agent must preserve brand constraints and required chart fields.
- Generated campaign revisions store final HTML/CSS immutably.
- Changing a template never changes historical campaigns.

Implemented baseline:

- Seed one active built-in template from the current layout.
- Add template metadata/config resolution.
- Record `template_id` and `template_version` on generated assets.
- Expose active template config and built-in options through `/api/config`.
- Add admin selector for the active built-in infographic template.
- Allow future S3-backed templates under the existing campaign assets bucket.

Remaining work:

- Add admin upload/versioning for S3-backed HTML/CSS template assets.
- Generate and store template preview PNGs.
- Add a template list/detail API rather than only config-backed selection.
- Move campaign output to revision records before adding custom template edits.

## Phase 3: Campaign Revisions

Status: initial backward-compatible implementation exists.

Purpose: make campaign outputs immutable while allowing refinement.

Campaign record:

```text
week_id
status: draft | revising | approved | published
active_revision_id
approved_revision_id
created_at
updated_at
```

Campaign revision:

```text
revision_id
week_id
parent_revision_id
source_instruction
template_id
template_version
brand_config_snapshot
prompt_versions
model_id
radio_reads
social_copy
infographic_html
infographic_css
png_s3_key
created_at
created_by
validation_results
```

Rules:

- Refinement creates a new revision.
- Approval pins one revision.
- Publishing uses the approved revision.
- Old revisions remain available for audit and comparison.

Implemented baseline:

- Completed campaign generations still write the existing `CAMPAIGN` item for
  UI/API compatibility.
- Completed campaign generations also write a `CAMPAIGN_REVISION` item with
  generated sections, infographic asset metadata, PNG metadata, generator
  metadata, and parent revision id.
- Campaign index items expose active/approved revision metadata when present.
- Revision list/detail APIs expose immutable revision records.
- The admin campaign modal shows available revision history.
- A revision can be approved by id, which promotes that revision as the active
  campaign snapshot and pins `approved_revision_id`.
- The admin campaign modal can compare two revisions side by side, including
  infographic preview, social summary, and sample DJ reads.

Remaining work:

- Add revision cleanup/export tooling.

## Phase 4: Agent-Authored HTML/CSS With Validation

Status: initial model-authored generation with validation and template fallback exists.

Purpose: make the infographic feel human-designed while keeping publishable
constraints.

Agent input:

- chart brief
- brand config snapshot
- selected template HTML/CSS
- previous visual memory
- style examples
- output contract

Agent output:

- final campaign-specific HTML
- final campaign-specific CSS
- short visual rationale
- self-review

Validation checks:

- `1280x720` canvas.
- logo placeholder exists.
- exact chart title exists.
- exact tag line exists.
- all top 10 ranks are present.
- artist/title/movement/play fields are represented.
- no external scripts.
- no external network assets.
- CSS/HTML size within limit.
- approved palette/font tokens are used.

Implemented baseline:

- Python-side infographic asset validation mirrors renderer safety checks.
- Validation enforces `1280x720`, non-empty HTML/CSS, blocked HTML/CSS
  patterns, logo placeholder, exact chart title, exact tag line, and chart
  content warnings.
- Campaign generation stores `infographic_asset_validation`.
- Rendering fails before Playwright invocation if blocking validation errors
  exist.
- Campaign and revision UI surfaces validation pass/fail details.
- When a model and infographic agent spec are available, campaign generation
  asks the model to author the final infographic HTML/CSS using chart facts,
  brand constraints, memory, and the selected template as context.
- Invalid model-authored HTML/CSS falls back to the active template render and
  records the model error in asset metadata.

Remaining work:

- Move this authored-asset path into Strands inside AgentCore Runtime.
- Add richer visual self-review/evaluation before rendering.
- Add human refinement instructions that create new revisions.

Failure behaviour:

- Store failed revision metadata and validation errors.
- Do not publish or approve failed assets.
- Allow regeneration after settings/template/prompt correction.

## Phase 5: Strands Agents Inside AgentCore Runtime

Status: initial runtime migration implemented.

Purpose: move from a thin AgentCore runtime plus coded orchestration to a
proper agent/tool framework while preserving deterministic workflow control.

Recommended shape:

```text
AgentCore Runtime
  -> workflow controller
  -> Strands agents for creative stages
  -> existing Lambda tools for facts, rendering, memory, and persistence
```

Initial agents:

- `CampaignPlannerAgent`
- `RadioReadAgent`
- `SocialCopyAgent`
- `InfographicDesignAgent`
- `FeedbackSummarizerAgent`

Rules:

- Workflow order remains deterministic.
- Strands owns creative generation, not factual calculations.
- Tools expose task capabilities, not raw API Gateway endpoints.
- AgentCore Memory is used for creative continuity only.

Implemented baseline:

- AgentCore Runtime now initializes a Strands `Agent`.
- Existing runtime actions are routed through Strands method-style tools.
- The public runtime action contract remains unchanged.
- Creative generation still happens in the Lambda-backed tool service until
  Prompt Management and stage-specific agents are introduced.
- The Lambda-backed creative generation path can now load versioned prompt
  templates from Bedrock Prompt Management before invoking the selected model.

Remaining work:

- Split creative stages into explicit Strands agents/tools.
- Add richer Strands workflow/state handling for refinement and feedback.

## Phase 6: Bedrock Prompt Management

Status: initial implementation exists.

Purpose: move hard-coded prompts into versioned AWS-managed prompt assets.

Prompt assets:

- radio read prompt
- social copy prompt
- infographic content prompt
- infographic HTML/CSS asset prompt
- campaign planner prompt
- infographic refinement prompt
- feedback summariser prompt
- visual memory summariser prompt

Rules:

- Prompt versions are recorded on each campaign revision.
- Production prompt versions are promoted deliberately.
- Prompt Management stores prompt templates and variables.
- DynamoDB stores which prompt versions were used for generated assets.

Implemented baseline:

- System config key `campaign_prompts` stores optional prompt identifiers and
  versions for `radio_reads`, `infographic`, `social`, and
  `infographic_asset`.
- Admin Settings exposes prompt identifier/version fields for those sections.
- AgentCore tools pass prompt config into campaign draft generation.
- Generation fetches prompts with Bedrock Prompt Management `GetPrompt`, renders
  `{{variable}}` placeholders locally, and appends a mandatory JSON output
  guard.
- Blank, missing, or failed managed prompts fall back to the built-in code
  prompt and record the fallback reason in campaign generator metadata.
- Campaign generator metadata records `prompt_refs` per generated section.

Remaining work:

- Create managed prompt assets in AWS and seed their initial content.
- Add prompt list/selection support instead of manual identifier entry.
- Move stage-specific prompt use into full Strands agents once those creative
  agents are split out.

## Phase 7: Feedback Capture

Status: initial implementation exists.

Purpose: capture reviewer judgement without making feedback immediately mutate
production prompts.

Feedback record:

```text
campaign_week_id
revision_id
asset_type: infographic | social | radio
rating: up | down
feedback_text
prompt_id
prompt_version
model_id
created_at
created_by
```

Rules:

- Thumbs up/down is useful only with optional free-text context.
- Raw feedback is stored for audit.
- Summarised preferences may be written to AgentCore Memory.
- Feedback does not directly rewrite prompts.

Implemented baseline:

- Campaign modal captures thumbs up/down and optional free-text feedback for
  infographic, social copy, and radio reads.
- Feedback is stored as immutable `CAMPAIGN_FEEDBACK` records in the campaigns
  table, scoped to week id, revision id, and asset type.
- Feedback records snapshot relevant prompt refs and model id from the reviewed
  revision.
- Authenticated API routes list and create revision feedback:
  `/api/campaigns/YYYY-MM-DD/revisions/REVISION_ID/feedback`.
- Admin feedback summary aggregates feedback by asset type, model, prompt ref,
  and recent negative comments.
- Authenticated API route:
  `/api/campaigns/feedback/summary`.
- Feedback summary reads use the campaigns table `gsi1` index with
  `gsi_pk = FEEDBACK_SUMMARY`.

Remaining work:

- Summarise repeated feedback themes into AgentCore Memory.
- Use feedback aggregates as the input to manual prompt optimisation.

## Phase 8: Manual Prompt Optimization And A/B Promotion

Status: planned.

Purpose: improve prompts from accumulated feedback while controlling cost and
production risk.

Trigger policy:

- No inline optimisation during campaign generation.
- No automatic prompt replacement.
- Admin manually starts optimisation after enough feedback exists.

Suggested readiness thresholds:

- 10+ rated revisions for an asset type.
- 5+ approved examples.
- repeated negative feedback on the same issue.
- current prompt version used across several campaigns.

Workflow:

```text
collect feedback
  -> build optimisation dataset
  -> estimate/run offline optimisation
  -> create candidate prompt version
  -> A/B compare old vs candidate
  -> admin promotes candidate or rejects it
```

Guardrail:

- Optimisation produces a candidate only.
- Admin promotion is required before production use.

## Phase 9: Campaign Refinement Chat

Status: planned after revisions and templates.

Purpose: allow the admin to shape a campaign asset through discrete creative
instructions.

Rules:

- Chat edits create new revisions.
- The approved revision remains immutable.
- Refinement instructions are stored with the revision.
- Accepted/rejected changes contribute to feedback and memory.

Example:

```text
User: Make this feel less neon and more premium radio poster.
Agent: Generates revision v2 with new HTML/CSS and PNG.
User: Make the facts panel more chart-specific.
Agent: Generates revision v3.
User: Approve v3.
System: Pins v3 as approved revision.
```

## Phase 10: Publishing Integrations

Status: future.

Purpose: publish approved campaign assets to external channels.

Rules:

- Only approved revisions can be published.
- Manual export/download remains available.
- Direct posting integrations are permission-scoped and optional.
- Publishing metadata is stored against the approved revision.

## Revert Boundary

This roadmap is documentation only. The next implementation work should be
introduced in narrow, reviewable commits:

1. Template store only.
2. Revision model only.
3. Agent-authored HTML/CSS only.
4. Strands creative-agent expansion only.
5. Prompt Management only.

Avoid mixing these layers in a single change unless explicitly approved.
