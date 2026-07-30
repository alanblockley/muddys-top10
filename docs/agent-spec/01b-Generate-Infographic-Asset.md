# Muddy's Top 10 Infographic Automation Agent

## Mission

Create the weekly **Muddy's Top 10** infographic as a final 1280 x 720 PNG.

The agent must design the weekly composition holistically from the supplied chart and campaign facts. It should not merely fill a fixed template. The output should feel like a human-built promotional chart poster: intentional hierarchy, chart-specific emphasis, polished spacing, and controlled variation from week to week.

The preferred path is now direct image generation from the stored template
reference PNG plus factual chart/campaign data. The HTML/CSS renderer remains a
safe fallback and template-reference generator, not the only production output
path.

The weekly process should be:

```text
Chart/campaign facts
        +
Stored template reference PNG
        ↓
Image-generation prompt with authoritative chart data
        ↓
Model-generated PNG
        ↓
S3 campaign asset
```

Fallback path:

```text
Chart/campaign facts
        +
Agent-authored HTML/CSS
        ↓
Safety validation
        ↓
Playwright render
        ↓
1280 × 720 PNG
```

The input data will be handled elsewhere. This project is responsible for validating that data, applying it to the fixed layout, and producing the final image.

## Source Reference

The supplied reference image is the authoritative visual specification:

```text
info-graphic-example.png
```

Expected source location when initially developing:

```text
../info-graphic-example.png
```

Do not abandon the Muddy's visual identity. Preserve the recognizable ingredients
from the references while allowing the agent to compose them intelligently for
the actual chart story that week.

The agent may vary layout emphasis, callouts, icon treatment, chart annotations,
stats placement, and visual rhythm when the data supports it. Variation must
remain professional, readable, and brand-consistent.

The final output canvas must be:

```text
Width:  1280 px
Height: 720 px
Aspect: 16:9
Format: PNG
```

## Required Implementation

Prefer the **template reference PNG + image-generation model** implementation
when an image-capable model is configured. Keep the **agent-authored
HTML/CSS/SVG plus Playwright** implementation as the deterministic fallback.

Recommended stack:

- Node.js
- TypeScript
- HTML and CSS
- Inline SVG for icons, borders, arrows, decorations, and simple artwork
- Playwright or Chromium for rendering
- JSON Schema or Zod for factual input and authored-output validation
- Vitest or Jest for tests

Do not use:

- OCR as part of the weekly rendering pipeline
- Canvas positioning based on guessed measurements at runtime
- Unvalidated free-form LLM output sent directly to a browser
- Remote scripts, fonts, images, icons, stylesheets, or tracking pixels
- Remote fonts, icons, stylesheets, or images required at render time

All assets and fonts required for rendering must be local to the project or replaced with appropriately licensed local alternatives.

## Key Principle

Separate facts and creative composition.

### Stable brand ingredients

The following elements should usually appear, but the agent may compose them in
the most effective arrangement for the week's story:

- Black background
- Purple, magenta, yellow, green, blue, red, and white visual palette
- Masthead and title treatment
- Muddy's dog logo placement
- Music Cafe script treatment
- Neon music-note decoration
- Top-right compiled-from caption
- Top 10 chart
- Chart Talk / weekly story area
- Statistics, facts, and numbers
- Lower promotional strip, venue banner, or equivalent CTA
- “Your Requests. Your Music. Your Chart.” brand line or badge
- Footer strapline
- Panel borders, separators, glows, and background effects
- Permanent show and venue wording unless configuration explicitly overrides it

### Required factual content

These values come from the supplied data and must not be invented:

- Date range
- Ten chart entries
- Play counts
- Movement state and amount
- Chart Talk headings and body copy
- Layout emphasis, callouts, icon treatment, and badges
- Weekly statistics
- Chart facts
- “Top 10 by the Numbers” values
- Any approved optional weekly badge values

The agent may rewrite presentation copy, but factual claims must be traceable to
the supplied data.

## Project Structure

Create or maintain this structure:

```text
.
├── AGENTS.md
├── package.json
├── tsconfig.json
├── README.md
├── assets/
│   ├── reference/
│   │   └── info-graphic-example.png
│   ├── brand/
│   │   ├── muddys-logo.png
│   │   ├── australian-flag.png
│   │   └── icons/
│   ├── fonts/
│   └── backgrounds/
├── schemas/
│   └── chart.schema.json
├── examples/
│   └── chart.example.json
├── src/
│   ├── cli.ts
│   ├── validate.ts
│   ├── render.ts
│   ├── types.ts
│   ├── template/
│   │   ├── index.html
│   │   ├── chart.css
│   │   └── chart.ts
│   └── helpers/
│       ├── text-fit.ts
│       ├── movement.ts
│       └── formatting.ts
├── tests/
│   ├── schema.test.ts
│   ├── movement.test.ts
│   ├── text-fit.test.ts
│   └── visual.test.ts
└── output/
```

The repository instruction file should normally be named `AGENTS.md` for Codex compatibility. This file may be renamed from `agent.md` to `AGENTS.md` when placed in the repository root.

## Authored Output Contract

The infographic agent should return authored HTML/CSS as two fenced code blocks.
Do not wrap the final HTML/CSS in JSON; large code strings are too fragile when
escaped into JSON.

```html
<section class="poster">
  ...
</section>
```

```css
.poster {
  width: 1280px;
  height: 720px;
}
```

The renderer will wrap the HTML in `#infographic`, inject approved local assets,
disable JavaScript, block network access, and capture the result as PNG.

Allowed asset placeholder:

```text
{{MUDDYS_LOGO_DATA_URI}}
```

### Authored HTML/CSS rules

- The agent owns the composition, spacing, typography choices, callout layout,
  visual rhythm, and weekly emphasis.
- The output must fit a `1280x720` canvas without scrolling or clipping.
- Include all text as selectable/rendered HTML text, not baked into an image.
- Use inline SVG or CSS for simple icons, arrows, dividers, glows, panels, and
  badges.
- Use the Muddy's logo placeholder when including the dog logo.
- Do not include JavaScript, event handlers, forms, iframes, external links,
  remote URLs, remote fonts, external CSS, or external images.
- Do not invent chart facts, ranks, movements, play counts, dates, hosts, or
  venue details.
- The HTML/CSS should be polished enough to render directly. It is not a prompt
  for another model.

## Factual Input Contract

Use a strict JSON structure similar to the following:

```json
{
  "layout": {
    "variant": "feature-climber",
    "featured_story": "biggest_climber"
  },
  "week": {
    "start": "2026-07-18",
    "end": "2026-07-25",
    "display": "JUL 18 – JUL 25, 2026"
  },
  "chart": [
    {
      "position": 1,
      "artist": "Ella Langley",
      "title": "Choosin' Texas",
      "plays": 16,
      "movement": {
        "type": "up",
        "places": 1
      }
    }
  ],
  "chartBadges": [
    {
      "position": 10,
      "label": "NEW ENTRY!",
      "tone": "new"
    }
  ],
  "chartTalk": [
    {
      "slot": 1,
      "kind": "new-number-one",
      "icon": "trophy",
      "emphasis": "normal",
      "heading": "NEW NUMBER ONE!",
      "body": "Ella Langley hits #1...",
      "short_body": "Ella Langley hits #1.",
      "metrics": {}
    }
  ],
  "stats": {
    "newEntries": 0,
    "climbers": 6,
    "fallers": 4,
    "nonMovers": 1
  },
  "facts": [
    "Just 1 play separates #1 and #2.",
    "Ella Langley earns her first #1.",
    "Bruno Mars remains the longest-running Top 10 hit."
  ],
  "numbers": {
    "totalPlaysThisWeek": 141,
    "totalPlaysLastWeek": 146,
    "percentageChange": -3.4,
    "weeksSinceLaunch": 12,
    "differentArtists": 10
  },
  "show": {
    "time": "2AM SLT",
    "day": "EVERY SATURDAY",
    "presenters": "DJ TOOHEY & JP"
  }
}
```

### Validation rules

- `chart` must contain exactly 10 entries.
- Positions must be unique integers from 1 through 10.
- Entries must be rendered in ascending position order regardless of input order.
- `plays` must be a non-negative integer.
- Movement types must be one of `new`, `up`, `down`, `same`, or `reentry`.
- `places` is required for `up` and `down`.
- `places` should be zero or omitted for `same`.
- All required weekly statistics must be supplied or deterministically calculated.
- No renderer should silently invent missing chart data.
- Validation errors must clearly identify the failing field.

## Movement Rendering Rules

Render movement consistently:

| Type | Symbol | Colour | Label example |
|---|---|---|---|
| `new` | star or approved new-entry symbol | yellow | `NEW` |
| `up` | upward arrow | green | `UP 5` |
| `down` | downward arrow | red | `DOWN 2` |
| `same` | horizontal dash | light grey | `NON-MOVER` |
| `reentry` | approved return symbol | blue or yellow | `RE-ENTRY` |

The large movement number and the smaller label must remain in their dedicated chart columns.

Never use emoji glyphs for final production icons. Use inline SVG or local vector assets so rendering is consistent across systems.

## Layout Specification

Use the reference image to measure and reproduce the layout.

### Major regions

1. **Header**
   - Dog logo at far left
   - “MUDDY'S TOP 10” in large condensed white lettering
   - “THIS WEEK” in purple
   - “Music Cafe” beneath in yellow script
   - Date range centred beneath the main title
   - Neon music notes toward the upper-right
   - Compilation explanation at far right

2. **Left chart**
   - Ten equal-height rows
   - Position block at far left
   - Artist and title field
   - Play count aligned toward the right of the title field
   - Movement icon and amount column
   - Movement label column
   - Crown marker for the number-one row

3. **Chart Talk**
   - Yellow brush-style heading
   - Six cells arranged as two columns by three rows
   - Stable icon position in every cell
   - Heading and body text aligned consistently
   - Dotted separators

4. **Lower statistics**
   - Three neighbouring panels: This Week's Stats, Chart Facts, and Top 10 by the Numbers

5. **Bottom promotion**
   - Weekly broadcast day and time
   - Presenter names
   - Australian branding
   - Venue call-to-action
   - Venue tagline
   - Circular requests/music/chart badge
   - Bottom footer strapline

### Coordinate management

Create a central layout token file or CSS custom properties for canvas dimensions, region boundaries, row heights, column widths, padding, border widths, font sizes, line heights, icon dimensions, colour values, and glow strengths.

Do not scatter unexplained pixel values throughout the code.

Example:

```css
:root {
  --canvas-width: 1280px;
  --canvas-height: 720px;
  --chart-left: 16px;
  --chart-top: 160px;
  --chart-width: 924px;
  --chart-row-height: 54px;
}
```

The exact values should be refined against the source reference.

## Typography

- Use local fonts only.
- Select close, appropriately licensed alternatives when the exact original fonts are unavailable.
- Define explicit fallback stacks.
- Do not depend on fonts installed on the host machine.
- Wait for `document.fonts.ready` before taking the screenshot.
- Track font files in the repository only when licensing permits.
- Never commit unlicensed commercial font files.

Suggested font roles:

- Main condensed display: bold condensed sans-serif
- Chart entry text: condensed sans-serif
- Labels and statistics: condensed sans-serif
- “Music Cafe” and small accent phrases: brush/script font
- Body copy: readable condensed or narrow sans-serif

## Text Fitting

Text fitting must be deterministic.

### Chart rows

- Artist and title should normally remain on one line.
- The play count must retain its reserved space.
- Begin with the standard chart-row font size.
- Reduce font size gradually only when text exceeds the available width.
- Enforce a minimum font size.
- If text still overflows at the minimum, truncate with an ellipsis and emit a warning.
- Never allow chart text to overlap movement columns.

### Chart Talk cells

- Heading has a fixed maximum of one line.
- Body copy may wrap.
- Limit body copy to the available height.
- Reduce body font size within a small approved range when required.
- If copy still overflows, fail validation or truncate only when a command-line flag explicitly permits it.
- Preserve meaningful punctuation and quotation marks.

Implement and test a shared text-fitting helper. Do not manually tune individual weeks.

## Colours

Derive exact values from the reference and centralise them. Do not introduce a new colour palette.

Semantic roles include near-black background, bright violet, deep violet, chart yellow, movement green, movement red, blue and pink Chart Talk accents, white primary typography, and grey secondary typography.

## Rendering

Provide a CLI such as:

```bash
npm run render -- \
  --input examples/chart.example.json \
  --output output/muddys-top-10-2026-07-25.png
```

The renderer must:

1. Read the authored HTML/CSS package.
2. Validate it against the allowed HTML/CSS rules.
3. Inject local assets and approved placeholders.
4. Wait for local fonts and assets.
5. Set viewport to exactly 1280×720.
6. Set device scale factor to 1 unless a separate high-resolution mode is explicitly implemented.
7. Disable animations and transitions.
8. Capture only the infographic root element.
9. Save a PNG.
10. Return a non-zero exit code on failure.

Recommended Playwright behaviour:

```ts
await page.setViewportSize({ width: 1280, height: 720 });
await page.emulateMedia({ reducedMotion: "reduce" });
await page.evaluate(() => document.fonts.ready);
await page.locator("#infographic").screenshot({
  path: outputPath,
  type: "png"
});
```

Do not use JPEG for the master output.

## Blank Template Output

Also support generating a clean blank template:

```bash
npm run render:blank -- \
  --output output/muddys-top-10-blank.png
```

The blank version must preserve the full background, logo and permanent branding, panels and borders, permanent headings, static promotional copy, permanent icons where appropriate, structural chart positions, and empty dynamic fields.

It must contain no weekly chart data, date, Chart Talk copy, movement values, or statistics.

The normal weekly generator should not require computer vision to interpret that PNG.

## Visual Regression Testing

Consistency is a primary requirement.

Create visual regression tests:

1. Render the included example JSON.
2. Compare it with an approved golden PNG.
3. Fail when pixel differences exceed a small documented threshold.
4. Save a diff image when the test fails.

The threshold may allow minor anti-aliasing differences but must catch shifted panels, changed row heights, incorrect fonts, missing icons, overflow, unexpected colour changes, and altered footer or header geometry.

Any deliberate design change must update the golden image as a conscious review step.

## Required Tests

At minimum, test:

- Schema rejects fewer or more than 10 chart entries.
- Schema rejects duplicate positions.
- Schema rejects invalid movement types.
- Chart sorting works.
- Movement labels are correct.
- Negative percentages render red.
- Long chart titles shrink but do not overlap.
- Chart Talk copy respects its cell.
- Missing assets fail loudly.
- The example fixture renders at 1280×720.
- Blank render contains no weekly content.
- Visual regression remains within tolerance.

## Logging and Error Handling

CLI output should be direct and useful.

```text
Validated: examples/chart.example.json
Loaded 10 chart entries
Loaded 6 Chart Talk items
Rendering at 1280x720
Written: output/muddys-top-10-2026-07-25.png
```

Warnings should identify problematic content. Failures must be explicit. Do not catch and suppress rendering or validation errors.

## Configuration

Stable show details may be stored in `config/show.json`:

```json
{
  "venueName": "MUDDY'S MUSIC CAFE",
  "venueTagline": "WHERE MUSIC & FRIENDS COME TOGETHER",
  "showDay": "EVERY SATURDAY",
  "showTime": "2AM SLT",
  "presenters": "DJ TOOHEY & JP",
  "presenterTagline": "The Australian Dynamic Duo!",
  "footerLeft": "YOUR REQUESTS. YOUR MUSIC. YOUR CHART.",
  "footerRight": "THANK YOU FOR KEEPING MUDDY'S PLAYING!",
  "compilationNote": "COMPILED FROM SONGS PLAYED BY OUR DJS AND PATRON REQUESTS"
}
```

Weekly data should not duplicate stable configuration unless overrides are intentionally supported.

## Deliverables

The completed project must include:

- Deterministic weekly renderer
- Recreated template
- Blank template renderer
- Strict input schema
- Example input
- Local asset handling
- CLI
- README with setup and usage
- Unit tests
- Visual regression test
- One approved example output
- One blank template output

## Acceptance Criteria

The work is complete when:

- One documented command produces a 1280×720 PNG.
- The output visually matches the established Muddy's Top 10 design.
- Re-running with identical input produces an identical or pixel-equivalent result.
- Updating only the JSON changes only the intended dynamic content.
- Long text is handled predictably.
- No internet access is required during rendering.
- No generative image model is involved.
- Missing or invalid data causes a clear failure rather than a plausible-looking invention.
- A blank reusable template can be generated separately.
- Automated tests protect the layout from accidental drift.

## Working Behaviour for Codex

When implementing this project:

1. Inspect the reference image before writing layout code.
2. Measure major panel boundaries and establish layout tokens first.
3. Build the locked background and structural panels.
4. Add dynamic chart rows.
5. Add movement rendering.
6. Add Chart Talk.
7. Add statistics and footer content.
8. Implement text fitting.
9. Add schema validation.
10. Add automated rendering.
11. Add tests and visual regression.
12. Document all commands.

Prefer incremental, reviewable commits.

Do not broadly refactor unrelated project code.

Do not replace supplied brand assets with invented alternatives without clearly documenting the limitation.

When exact reproduction is blocked by a missing asset or font, preserve geometry and visual hierarchy, use the closest licensed local substitute, and record the difference in `README.md`.

Do not claim pixel-perfect reproduction unless visual comparison supports that claim.
