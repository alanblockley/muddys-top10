# AntV Infographic Template System — Implementation Plan

## Overview

Replace the current HTML/CSS code generation approach (Claude authoring HTML → Playwright rendering) with AntV Infographic — a declarative template engine that separates design from data. Templates are designed visually in the admin UI and rendered server-side to PNG during campaign generation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Admin UI — Template Editor                                       │
│                                                                  │
│  @antv/infographic (CDN, editable: true)                        │
│  - Load existing template spec from config                       │
│  - Live preview with sample chart data                           │
│  - Edit layout, colours, structure visually                      │
│  - Save template spec (JSON/syntax string) to S3 via API         │
│                                                                  │
└─────────────┬───────────────────────────────────────────────────┘
              │ saves template spec
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ S3: campaign-assets/templates/antv/{name}.json                   │
│ - Template syntax/spec                                           │
│ - Metadata (name, version, created_by, etc.)                     │
└─────────────┬───────────────────────────────────────────────────┘
              │ loaded at generation time
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Campaign Generation (AgentCore Tools Lambda)                     │
│                                                                  │
│  1. Load template spec from S3                                   │
│  2. Claude generates editorial content (chart story, headline,   │
│     which stats to highlight) — text only                        │
│  3. Build data payload: chart_brief tracks + editorial content   │
│  4. Invoke Infographic Renderer Lambda with spec + data          │
│                                                                  │
└─────────────┬───────────────────────────────────────────────────┘
              │ invokes
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Infographic Renderer Lambda (Node.js)                            │
│                                                                  │
│  import { renderToString } from '@antv/infographic/ssr'          │
│  - Receives: template spec + data payload                        │
│  - Renders to SVG string                                         │
│  - Converts SVG → PNG (sharp or resvg-js)                        │
│  - Uploads PNG to S3                                             │
│  - Returns PNG metadata                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## What Claude does vs what the template engine does

| Responsibility | Owner |
|---|---|
| Layout, colours, fonts, positioning, visual hierarchy | Template (designed once, editable in UI) |
| Track data (ranks, artists, titles, play counts, movement) | Deterministic (from chart_brief) |
| Editorial content (headline angle, chart story, stat highlights) | Claude (per generation) |
| Rendering to PNG | AntV Infographic SSR + SVG→PNG conversion |

## Custom Template Requirements

A "Muddy's Top 10 Chart Poster" custom template that defines:
- 1280×720 fixed canvas
- Dark background with neon/purple accent palette
- Header region: logo, chart title, date range
- Chart region: 10 ranked entries with artist, title, play count, movement indicator
- Stats region: new entries, climbers, fallers, non-movers
- Chart story region: headline + narrative text
- Footer: show time, presenters, tagline

## Data Contract (template input)

```json
{
  "chart_title": "Muddy's Top 10",
  "tagline": "Your requests. Your music. Your chart.",
  "week_display": "JUL 25 – AUG 1, 2026",
  "headline": "New number one as Olivia Dean takes the crown",
  "chart_story": "After three weeks climbing...",
  "tracks": [
    { "rank": 1, "artist": "Olivia Dean", "title": "Man I Need", "plays": 33, "movement": "up", "delta": 3 },
    { "rank": 2, "artist": "Alex Warren", "title": "FEVER DREAM", "plays": 30, "movement": "up", "delta": 1 },
    { "rank": 3, "artist": "Bruno Mars", "title": "I Just Might", "plays": 29, "movement": "down", "delta": -2 },
    { "rank": 4, "artist": "BTS", "title": "SWIM", "plays": 29, "movement": "down", "delta": -2 },
    { "rank": 5, "artist": "Harry Styles", "title": "Ready, Steady, Go!", "plays": 23, "movement": "up", "delta": 2 },
    { "rank": 6, "artist": "The Weeknd", "title": "Open Hearts", "plays": 20, "movement": "new", "delta": null },
    { "rank": 7, "artist": "Dua Lipa", "title": "Illusion", "plays": 18, "movement": "down", "delta": -3 },
    { "rank": 8, "artist": "Sabrina Carpenter", "title": "Taste", "plays": 16, "movement": "up", "delta": 4 },
    { "rank": 9, "artist": "Billie Eilish", "title": "Birds of a Feather", "plays": 14, "movement": "same", "delta": 0 },
    { "rank": 10, "artist": "Taylor Swift", "title": "Fortnight", "plays": 12, "movement": "reentry", "delta": null }
  ],
  "stats": { "new_entries": 1, "climbers": 5, "fallers": 3, "non_movers": 1 },
  "show": { "time": "2AM SLT", "day": "EVERY SATURDAY", "presenters": "DJ TOOHEY & JP" },
  "logo_url": "{{MUDDYS_LOGO_DATA_URI}}"
}
```

## Key Technical Decisions

1. **CDN for frontend** — no build step, load @antv/infographic from unpkg/cdnjs in admin.html
2. **Node.js SSR for Lambda** — `@antv/infographic/ssr` + `renderToString()` → SVG string
3. **SVG → PNG conversion** — use `@resvg/resvg-js` (pure Rust WASM, works in Lambda without native deps) or `sharp`
4. **Template stored as syntax string** — the AntV declarative syntax or JSON spec, saved to S3
5. **Remove Playwright dependency for infographics** — AntV renders server-side without a browser
6. **Keep Playwright Lambda available** — only for legacy/edge cases, not the primary path

## Implementation Tasks

### Task 1: Spike — AntV SSR Rendering (2-3 hours)
- Install `@antv/infographic` in `infographic-renderer/`
- Create a test script that renders a 10-item chart list to SVG using `renderToString()`
- Convert SVG to PNG using `@resvg/resvg-js` or `sharp`
- Verify output is 1280×720 and contains readable text
- **Validates:** Can AntV produce a chart poster quality output server-side?

### Task 2: Custom Muddy's Template (3-4 hours)
- Design the chart poster template using AntV's custom template/structure system
- Match the V3 reference design: dark bg, neon accents, ranked chart table, stats, story
- Define data binding: how chart_brief maps to template data slots
- Test with sample data in the spike environment
- **Produces:** A reusable AntV template spec for the Muddy's Top 10 poster

### Task 3: Update Infographic Renderer Lambda (2 hours)
- Replace/augment `app.js` to accept AntV template spec + data payload
- Render via `renderToString()` → SVG
- Convert SVG → PNG (1280×720)
- Upload PNG to S3
- Keep Lambda contract compatible (same input/output shape where possible)
- Update `package.json` dependencies

### Task 4: Admin Template Editor (2-3 hours)
- Load `@antv/infographic` from CDN in admin.html
- Add "Template Editor" section in the Settings tab
- Initialize with `editable: true` and the saved template spec
- Show live preview with sample chart data
- Add Save button that stores the template spec

### Task 5: Template Save/Load API (1 hour)
- API endpoint to save AntV template spec to S3 (`templates/antv/{name}.json`)
- API endpoint to load the active template spec
- Update config to reference the active AntV template
- Integrate with the existing template selection dropdown

### Task 6: Campaign Generation Integration (2 hours)
- In agentcore-tools `create_chart_campaign`:
  - Load the active AntV template spec from S3
  - Build data payload from `chart_brief` + `infographic` (editorial content from Claude)
  - Invoke the updated renderer Lambda with `{template_spec, data}`
  - Store the returned PNG metadata on the campaign record
- Claude's role becomes: generate `infographic` content (headline, chart_story, stats to feature)
- Template's role: everything visual

### Task 7: Remove Old Code (1 hour)
- Delete from `campaign_generation.py`:
  - `generate_infographic_asset_with_model` (Claude HTML/CSS authoring)
  - `build_infographic_asset_prompt` and `build_infographic_asset_prompt_package`
  - `extract_infographic_asset_output`
  - `CLASSIC_CHART_POSTER_HTML` and `CLASSIC_CHART_POSTER_CSS`
  - `infographic_template_reference_images`
  - `render_asset_chart_row`, `render_asset_talk_card`
  - Related helper functions for HTML asset generation
- Delete from `infographic_templates.py`:
  - Classic poster template constants
  - `render_template` (token substitution for old HTML templates)
- Delete from `infographic_asset_validator.py`:
  - Replace with a simpler validator that checks: data payload is valid, template spec exists
- Keep:
  - `generate_infographic_content` / `generate_infographic_content_with_model` (editorial text)
  - Template upload/listing APIs (reused for AntV specs)
  - Presigned URL upload flow (for logo/assets)

### Task 8: End-to-End Test and Deploy (1 hour)
- Deploy to dev with `--force-agentcore-runtime-update`
- Trigger campaign generation
- Verify:
  - Claude generates editorial content (headline, chart story)
  - AntV renderer produces a 1280×720 PNG with correct data
  - PNG is stored in S3 and visible in the campaign record
  - Admin template editor loads and can modify the template
- Fix any integration issues

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| AntV custom templates may not support the exact Muddy's layout | Task 1 spike validates this before committing. Fallback: use AntV for structure + CSS overrides |
| SVG→PNG conversion quality (fonts, colours) | Test with @resvg/resvg-js which handles SVG faithfully. Alternative: Playwright on the SVG |
| Lambda cold start with @antv/infographic package | Profile in spike. If too slow, consider provisioned concurrency or lighter SSR alternative |
| AntV is primarily Chinese-documented | Core API is in English, syntax is language-agnostic. Gallery has examples we can reference |

## Success Criteria

1. Campaign generates a professional 1280×720 PNG without Claude writing any HTML/CSS
2. Admin can visually edit the template and see live preview
3. Chart data (all 10 tracks, movements, stats) renders accurately every time
4. Template changes take effect on next campaign generation without code deploy
5. No Playwright/headless browser required for infographic rendering
