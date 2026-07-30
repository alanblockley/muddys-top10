# Muddy's Infographic Renderer

Renderer for the weekly Muddy's Top 10 infographic.

The preferred agentic path renders **agent-authored HTML/CSS** to a `1280x720`
PNG using Playwright/Chromium. The agent owns the complete composition, while
this renderer owns guardrails: canvas size, blocked script/network content,
approved local assets, and final PNG capture.

The older fixed-template renderer remains available as a fallback, but it is no
longer the target creative architecture.

## Setup

```bash
cd infographic-renderer
npm install
npx playwright install chromium
```

## Render Example

Render agent-authored HTML/CSS:

```bash
npm run render:authored -- \
  --input examples/authored-infographic.example.json \
  --output output/muddys-top-10-authored.png
```

Render the legacy structured-template example:

```bash
npm run render -- \
  --input examples/chart.example.json \
  --output output/muddys-top-10-example.png
```

## Render Blank Template

```bash
npm run render:blank -- \
  --output output/muddys-top-10-blank.png
```

## Test

```bash
npm test
```

## Authored Input Contract

Use this path for AgentCore-generated infographic assets:

```json
{
  "canvas": {
    "width": 1280,
    "height": 720
  },
  "html": "<section class=\"poster\">...</section>",
  "css": ".poster { ... }"
}
```

Rules:

- `canvas` must be exactly `1280x720`.
- `html` and `css` must be complete enough to render the full composition.
- Use `{{MUDDYS_LOGO_DATA_URI}}` where the dog logo should be injected.
- Do not include scripts, event handlers, iframes, embeds, remote URLs,
  external stylesheets, or remote fonts.
- The agent should receive the relevant chart/campaign data and create the
  visual hierarchy holistically rather than filling fixed slots.

## Legacy Structured Input Contract

The input schema is defined in `schemas/chart.schema.json`. The core dynamic
sections are:

- `week`: display date range.
- `layout`: approved renderer variant and featured story intent.
- `chart`: exactly 10 chart entries.
- `chartBadges`: optional row badges such as `NEW ENTRY!`.
- `chartTalk`: exactly 6 editorial cells with approved icon and emphasis hints.
- `stats`: this week's movement statistics.
- `facts`: exactly 3 chart facts.
- `numbers`: the lower-right numeric panel.
- `show`: stable show details, with defaults allowed.

## Design Reference

The current source design reference is:

```text
../info-graphic-example.png
```

The production renderer targets `1280x720`, so the reference image informs
visual language, region hierarchy, palette, and styling rather than exact source
pixel dimensions.

## Creative Boundary

AgentCore should author the actual HTML/CSS layout for each week so the output
can feel human-designed and specific to the story of that chart. The renderer
should not decide composition beyond hard safety and output constraints.

Stable constraints:

- Canvas: `1280x720`.
- Format: PNG.
- Brand: Muddy's logo, Top 10 identity, Music Cafe, weekly chart, Chart Talk,
  stats/facts/numbers, venue/show CTA.
- Inputs: factual campaign/chart data only; do not invent chart facts.
- Runtime: no network, no JavaScript execution, local assets only.
