# Output Contracts

This document defines the planned structured contracts between deterministic
services, AgentCore tools, and production agents.

## Chart Brief

The `chart_brief` is the primary factual input. It must be generated
deterministically from `top10_history` and related config.

For historical campaigns, the brief must be temporally bounded. A campaign for
one week may use that week's snapshot plus earlier snapshots only. Later weeks
must not affect `weeks_on_chart`, `best_rank`, `last_seen_week`, notables, or
memory context.

Required fields:

```json
{
  "week_id": "YYYY-MM-DD",
  "source_snapshot_key": "WEEK#YYYY-MM-DD",
  "chart_date": "ISO-8601",
  "week_start": "ISO-8601",
  "week_end": "ISO-8601",
  "venue_timezone": "SLT",
  "chart_config": {},
  "filter_patterns": [],
  "tracks": [],
  "notables": {},
  "summary": {}
}
```

Each track should include:

```json
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
  "last_seen_week": "YYYY-MM-DD"
}
```

## Campaign Context

The campaign context wraps the chart brief with generation instructions.

```json
{
  "campaign_id": "WEEK#YYYY-MM-DD",
  "week_id": "YYYY-MM-DD",
  "chart_brief": {},
  "venue_config": {},
  "brand_config_snapshot": {},
  "infographic_template": {},
  "context_refs": [],
  "agent_specs": [],
  "prompt_versions": {},
  "generation_options": {}
}
```

`context_refs` should contain file paths and content hashes for any markdown
context files used.

## Campaign Branding

Campaign branding is system-level configuration. It is resolved before campaign
generation and stored as a snapshot on each campaign revision.

```json
{
  "logo_variant": "uploaded",
  "logo_s3_key": "branding/logo-2026-07-28T00-00-00.png",
  "logo_content_type": "image/png",
  "logo_filename": "logo.png",
  "logo_alt": "Muddy's Music Cafe logo",
  "chart_title": "Muddy's Top 10",
  "chart_title_text": "Muddy's Top 10",
  "tagline": "Your requests. Your music. Your chart.",
  "tagline_text": "Your requests. Your music. Your chart.",
  "color_scheme": "custom",
  "primary_color": "#a855f7",
  "secondary_color": "#facc15",
  "accent_color": "#d946ef",
  "background_color": "#050005",
  "text_color": "#f8fafc",
  "font_family": "georgia",
  "font_family_css": "Georgia, serif"
}
```

Non-negotiable:

- logo
- chart title
- tag line

Creative but bounded:

- colour scheme
- font family

## Infographic Template

Infographic templates are versioned layout inputs. They are not final campaign
assets.

```json
{
  "template_id": "classic_chart_poster",
  "version": "1",
  "name": "Classic Chart Poster",
  "description": "Dense chart table with right-side chart facts panel.",
  "status": "active",
  "s3_html_key": "templates/classic_chart_poster/1/template.html",
  "s3_css_key": "templates/classic_chart_poster/1/template.css",
  "reference_png_key": "templates/classic_chart_poster/v1/reference-2026-07-30T00-00-00-000Z.png",
  "reference_png_generated_at": "2026-07-30T00:00:00.000Z"
}
```

The generation prompt may include the selected template HTML/CSS as a starting
point. The agent may adapt layout details but must preserve brand constraints,
chart fields, and the `1280x720` output target.

The admin UI can render a template reference PNG from the currently saved
branding and template. This PNG should use neutral placeholders, not real songs,
so it acts as a creative layout/brand basis rather than source data. Future
campaign generation uses this PNG as optional visual context alongside the
template HTML/CSS and factual chart data. The reference PNG is a system/template
asset, not a campaign asset, so clearing or deleting campaigns does not remove
it.

## Campaign Prompt Config

Prompt Management is optional per section. Blank prompt identifiers mean the
built-in code prompt is used.

```json
{
  "radio_reads": {
    "prompt_identifier": "prompt-id-or-arn",
    "prompt_version": "1",
    "variant_name": ""
  },
  "infographic": {
    "prompt_identifier": "prompt-id-or-arn",
    "prompt_version": "1",
    "variant_name": ""
  },
  "social": {
    "prompt_identifier": "prompt-id-or-arn",
    "prompt_version": "1",
    "variant_name": ""
  },
  "infographic_asset": {
    "prompt_identifier": "prompt-id-or-arn",
    "prompt_version": "1",
    "variant_name": ""
  }
}
```

Managed prompt templates may reference these variables:

- `section_name`
- `agent_spec`
- `personal_context`
- `memory_context`
- `venue_config_json`
- `chart_brief_json`
- `output_schema_json`
- `infographic_json` for infographic asset generation
- `template_metadata_json` for infographic asset generation
- `template_html` for infographic asset generation
- `template_css` for infographic asset generation

Generated campaign metadata records prompt source per section:

```json
{
  "generator": {
    "prompt_refs": {
      "radio_reads": {
        "source": "bedrock_prompt_management",
        "prompt_identifier": "prompt-id-or-arn",
        "prompt_version": "1",
        "prompt_arn": "arn:aws:bedrock:...",
        "variant_name": "default"
      }
    }
  }
}
```

## Radio Reads Output

Generated by the Radio Reads Generator spec.

```json
{
  "intro": "string",
  "top10_intro": "string",
  "top5_recap": "string",
  "top3_recap": "string",
  "outro": "string",
  "position_reads": [
    {
      "rank": 1,
      "track": "Artist - Title",
      "intro_line": "string",
      "movement_line": "string",
      "readout": "string",
      "outro_hook": "string"
    }
  ],
  "self_review": {
    "facts_verified": true,
    "pg_broadcast_appropriate": true,
    "missing_inputs": []
  }
}
```

## Infographic Asset Revision Output

Generated by the Infographic Design Agent after it receives chart facts,
branding, memory, and the selected template.

```json
{
  "html": "string",
  "css": "string",
  "visual_rationale": "string",
  "self_review": {
    "facts_verified": true,
    "brand_constraints_preserved": true,
    "template_used": true,
    "ready_for_render": true,
    "missing_inputs": []
  }
}
```

Required validation:

- exact chart title appears
- exact tag line appears
- logo placeholder appears
- all 10 ranks appear
- artist/title/movement/play fields are represented
- no external scripts
- no external network assets
- canvas remains `1280x720`

## Infographic Output

Generated by the Infographic Generator spec.

```json
{
  "headline": "string",
  "subhead": "string",
  "chart_story": "string",
  "movement_summary": "string",
  "statistics": [],
  "track_cards": [
    {
      "rank": 1,
      "display_text": "Artist - Title",
      "movement_badge": "Up 2",
      "supporting_line": "string"
    }
  ],
  "promotional_footer": "string",
  "self_review": {
    "facts_verified": true,
    "ready_for_publication": true,
    "missing_inputs": []
  }
}
```

## Social Output

Generated by the Social Media Generator spec.

```json
{
  "facebook": {
    "post": "string",
    "hashtags": []
  },
  "discord": {
    "post": "string"
  },
  "teaser": {
    "short_copy": "string"
  },
  "alt_text": "string",
  "self_review": {
    "facts_verified": true,
    "pg_appropriate": true,
    "missing_inputs": []
  }
}
```

## Campaign Draft

Persist generated output as a draft before any publishing action.

```json
{
  "pk": "CAMPAIGN",
  "sk": "WEEK#YYYY-MM-DD",
  "week_id": "YYYY-MM-DD",
  "status": "draft",
  "chart_brief": {},
  "radio_reads": {},
  "infographic": {},
  "social": {},
  "generated_at": "ISO-8601",
  "generator": {
    "model": "string",
    "prompt_version": "string",
    "agent_spec_versions": {},
    "context_refs": []
  },
  "review": {}
}
```

## Campaign Revision

Campaign revisions are the immutable unit of generated campaign content.

```json
{
  "pk": "CAMPAIGN_REVISION",
  "sk": "WEEK#YYYY-MM-DD#REV#revision-id",
  "week_id": "YYYY-MM-DD",
  "revision_id": "revision-id",
  "parent_revision_id": "revision-id",
  "source_instruction": "string",
  "template_id": "classic_chart_poster",
  "template_version": "1",
  "brand_config_snapshot": {},
  "prompt_versions": {},
  "model_id": "deepseek.v3.2",
  "radio_reads": {},
  "social": {},
  "infographic_asset": {
    "html": "string",
    "css": "string"
  },
  "infographic_png": {
    "bucket": "string",
    "key": "string",
    "content_type": "image/png",
    "width": 1280,
    "height": 720,
    "generation_mode": "model_image",
    "model": "image-model-id",
    "reference_png_key": "templates/classic_chart_poster/v1/reference.png"
  },
  "validation_results": {},
  "created_at": "ISO-8601",
  "created_by": "string"
}
```

`infographic_png.generation_mode` may be:

- `model_image`: final PNG was generated directly by the configured image model from the template reference PNG plus chart data.
- absent or renderer-specific: final PNG was rendered from stored HTML/CSS by the Playwright renderer fallback.

Campaign records should point to active and approved revisions:

```json
{
  "week_id": "YYYY-MM-DD",
  "active_revision_id": "revision-id",
  "approved_revision_id": "revision-id",
  "status": "draft"
}
```

## Feedback Record

Feedback records power memory summaries and future prompt optimisation.

```json
{
  "pk": "CAMPAIGN_FEEDBACK",
  "sk": "WEEK#YYYY-MM-DD#REV#revision-id#ASSET#infographic#TS#ISO-8601",
  "gsi_pk": "FEEDBACK_SUMMARY",
  "gsi_sk": "TS#ISO-8601#WEEK#YYYY-MM-DD#REV#revision-id#ASSET#infographic",
  "week_id": "YYYY-MM-DD",
  "revision_id": "revision-id",
  "asset_type": "infographic",
  "rating": "up",
  "feedback_text": "string",
  "prompt_refs": {},
  "model_id": "deepseek.v3.2",
  "created_at": "ISO-8601",
  "created_by": "string"
}
```

Current valid asset types are `infographic`, `social`, and `radio`.
