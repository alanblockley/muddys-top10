# Context Packs

Context packs define the editorial inputs that surround the deterministic chart
brief. They let the agents sound like Muddy's without hard-coding venue details
or personal style inside code.

## Authoritative Agent Specs

The files in `docs/agent-spec/` are the authoritative production-agent specs:

- `01a-Infographic-Agent-v3.md`
- `01b-Generate-Infographic-Asset.md`
- `02-Social-Agent-v3.md`
- `03-Radio-Agent-v3.md`

They define:

- objective
- agent role
- configurable venue context
- editorial policy
- expected inputs
- expected outputs
- validation checklist
- failure behaviour
- acceptance tests

## Personal Context Slots

Leave these files available for user-provided context. They can start empty and
be expanded over time.

```text
docs/agentic/context/personal-voice.md
docs/agentic/context/dj-toohey-style.md
docs/agentic/context/muddys-venue-context.md
docs/agentic/context/social-style-examples.md
docs/agentic/context/radio-read-examples.md
docs/agentic/context/infographic-style-examples.md
docs/agentic/context/words-and-phrases.md
docs/agentic/context/never-say.md
```

## Precedence Rules

When building an agent prompt/context package, apply context in this order:

1. System safety and application policy.
2. Deterministic chart facts from `chart_brief`.
3. System branding non-negotiables.
4. Selected versioned infographic template, when generating visual assets.
5. The relevant source agent spec from `docs/agent-spec/`.
6. Runtime venue configuration supplied by the application.
7. Bedrock Prompt Management prompt version.
8. Personal/context markdown from `docs/agentic/context/`.
9. Retrieved AgentCore Memory for editorial continuity.
10. Per-request user instructions.

If two inputs conflict:

- chart facts win over style
- chart facts win over AgentCore Memory
- temporal boundaries win over all context; do not use future weeks or future memory for historical campaigns
- logo, exact chart title, and exact tag line are non-negotiable
- runtime venue config wins over defaults in the agent spec
- selected colour scheme and font constrain visual creativity
- selected templates guide layout but do not override brand constraints
- safety and content-rating requirements win over personal style
- missing facts must be reported rather than invented

## Runtime Venue Config

The source specs include example venue configuration. Those values are context
only and must remain configurable.

The campaign generator should accept a resolved config object similar to:

```json
{
  "venue": {
    "name": "Muddy's Music Cafe",
    "world": "Second Life",
    "timezone": "SLT",
    "countdown_day": "Saturday",
    "countdown_time": "2:00am SLT",
    "hosts": {
      "primary": "DJ Toohey",
      "cohost": "JP"
    },
    "chart_basis": "Songs played at the venue during the previous 7 days plus listener requests.",
    "audience": {
      "style": "Friendly, community-driven internet radio",
      "content_rating": "PG"
    },
    "branding": {
      "tagline": "Your requests. Your music. Your chart.",
      "chart_title": "Muddy's Top 10",
      "primary_color": "#a855f7",
      "secondary_color": "#facc15",
      "font_family_css": "'Arial Narrow','Trebuchet MS',sans-serif"
    }
  }
}
```

## Infographic Template Context

Infographic generation should receive the active template as a context object.

```json
{
  "template_id": "classic_chart_poster",
  "template_version": "1",
  "template_html": "...",
  "template_css": "...",
  "design_intent": "Dense branded chart poster with table, stats, and show information."
}
```

The template is a starting point. The agent may adapt the layout, but the final
HTML/CSS must pass validation and must be stored immutably against the campaign
revision.

## Prompt Management Context

Generation prompts should be loaded from Bedrock Prompt Management once that
integration exists.

Prompt context should record:

- prompt id
- prompt version
- prompt variant, if used
- model id
- template id/version
- brand config snapshot hash

Prompt optimisation must not automatically replace production prompts. It
creates candidates that an admin can A/B test and promote.

## Prompt Assembly Contract

Each generation request should assemble:

- `chart_brief`
- relevant agent spec markdown
- venue config
- brand config snapshot
- selected infographic template, for visual generation
- Bedrock Prompt Management prompt version
- selected personal context markdown
- retrieved AgentCore Memory records, when configured
- output schema
- generation options such as platform, timing target, or tone

The assembled context should be versioned so campaign drafts record which inputs
produced them.
