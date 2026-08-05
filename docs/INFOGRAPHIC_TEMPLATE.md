# Infographic Template Guide

How to manually modify the chart PNG template used by the Muddy's Top 10 infographic renderer.

---

## File Location

```
src/infographic-renderer/chart-poster.js
```

This is a single self-contained file — no external template files are needed. It exports two functions:

- `buildPosterHtml(data)` — builds a complete HTML document with inline CSS
- `renderToPng(data, options)` — calls `buildPosterHtml`, then renders it to PNG via Playwright

---

## Rendering Pipeline

```
AgentCoreTools (Python)
    │
    │  Assembles data contract
    │  (src/agentcore-tools/app.py)
    │
    ▼
InfographicRendererFunction (Node.js 20.x)
    │
    │  buildPosterHtml(data) → HTML string
    │
    ▼
Playwright (Chromium headless)
    │
    │  Renders HTML at 1280×720 viewport
    │  Screenshots to PNG buffer
    │
    ▼
S3 Bucket
    │
    │  Stored as campaign asset
    │
    ▼
CloudFront → Public page / Admin UI
```

### Canvas Constraint

The output is always **1280×720 pixels** (landscape). The HTML viewport is set to this exact size and Playwright captures a full-page screenshot at this resolution. All layout decisions must fit within this fixed canvas.

---

## Data Contract

The `buildPosterHtml(data)` function receives a single object with this shape:

```javascript
{
  // Branding colours (from admin Settings → Branding)
  branding: {
    primary_color: "#hexval",
    secondary_color: "#hexval",
    accent_color: "#hexval",
    background_color: "#hexval",
    text_color: "#hexval"
  },

  // Top 10 tracks
  tracks: [
    {
      rank: 1,
      artist: "Artist Name",
      title: "Song Title",
      plays: 42,
      movement: "up",       // "up" | "down" | "new" | "same" | "reentry"
      delta: 3,             // positions moved (0 for new/same)
      weeks_on_chart: 5,
      best_rank: 1
    }
    // ... 10 items
  ],

  // Aggregate stats
  stats: {
    new_entries: 2,
    climbers: 4,
    fallers: 2,
    non_movers: 2
  },

  // Chart Talk cells (6 items, displayed in 2×3 grid)
  chart_talk: [
    {
      icon: "fa-crown",      // Font Awesome icon class
      headline: "Short Title",
      body: "Commentary text about this track/trend"
    }
    // ... 6 items
  ],

  // Show metadata
  show: {},

  // Display strings
  week_display: "Week ending 3 August 2026",
  week_id: "2026-08-03",
  tagline: "The Hottest Tracks in Second Life",
  headline: "Chart Headline",
  chart_story: "Narrative summary of chart movement",
  chart_title: "Muddy's Top 10",

  // Asset URLs (base64 data URIs at render time)
  logo_url: "data:image/png;base64,...",
  background_url: "data:image/jpeg;base64,...",
  fa_font_url: "data:font/woff2;base64,..."
}
```

### Where Data Is Assembled

The data contract is built in `src/agentcore-tools/app.py`. The AgentCore Tools function:
1. Reads chart data from ChartHistory table
2. Reads branding from Config table
3. Receives AI-generated editorial content (chart_talk, chart_story) from Claude
4. Loads logo, background image, and Font Awesome font as base64 data URIs
5. Invokes InfographicRendererFunction with the assembled payload

---

## Layout Structure

The poster uses CSS Grid with three rows:

```
grid-template-rows: 140px 1fr 100px
```

### Header (140px)

- Logo image (127×127px)
- Venue name + chart title
- Tagline
- Week display string

### Chart Section (flexible middle)

Two-column layout:

```
grid-template-columns: 1fr 1fr
```

**Left Column — Track Table:**
- 10 rows, each containing:
  - Rank badge (circular, coloured by movement type)
  - Artist name
  - Song title
  - Play count
  - Movement indicator arrow with delta

**Right Column — Sidebar:**
- "Chart Talk" header
- 6-cell grid (2 columns × 3 rows) with icon, headline, body per cell
- Stats strip (2 panels):
  - Panel 1: "Chart Story" — headline + narrative paragraph
  - Panel 2: "This Week's Stats" — new entries, climbers, fallers, non-movers counts

### Footer (100px)

- Show info (day and time)
- Divider line
- Hosts
- "Compiled by" tagline

---

## Movement Colour Coding

| Movement | Colour | Icon |
|----------|--------|------|
| `up` | Green | ▲ arrow |
| `down` | Red | ▼ arrow |
| `new` | Gold | ★ star |
| `same` | Grey | ● dot |
| `reentry` | Blue | ↺ re-entry |

---

## Chart Talk Fallback

If no AI-generated `chart_talk` array is provided (or it has fewer than 6 items), the template auto-generates cells from track data using this priority order:

1. Chart leader (highest rank)
2. Biggest climber (largest positive delta)
3. New entry
4. Re-entry
5. Biggest faller (largest negative delta)
6. Non-mover
7. Second climber
8. Longest-running (most weeks_on_chart)
9. New peak (best_rank equals current rank)
10. Any remaining track

No duplicate artists are used across the 6 cells.

---

## Branding Integration

Colours from **Admin UI → Settings → Branding** are injected as CSS custom properties and used throughout:

| Admin Setting | CSS Usage |
|---------------|-----------|
| Primary colour | Header background, rank badges, section headers |
| Secondary colour | Sidebar background, footer |
| Accent colour | Movement highlights, Chart Talk icons, stat numbers |
| Background colour | Page background, card backgrounds |
| Text colour | Body text, table text |

The **logo** and **chart title** from branding settings also appear in the header area.

To change the colour scheme: update colours in Admin → Settings → Branding, then regenerate the campaign. Previously generated PNGs are not affected.

---

## Making Design Changes

All design changes are made by editing `buildPosterHtml()` in `chart-poster.js`.

### Changing Colours/Typography

Edit the CSS within the template string. Colours reference the `branding` object properties:

```javascript
background-color: ${data.branding.primary_color};
color: ${data.branding.text_color};
font-family: 'Your Font', sans-serif;
```

### Changing Layout

Modify the CSS Grid properties:
- Overall layout: `grid-template-rows` on the container
- Chart section split: `grid-template-columns`
- Chart Talk grid: `grid-template-columns` and `grid-template-rows` on the talk container

### Adding/Removing Sections

Edit the HTML structure within `buildPosterHtml()`. The function returns a complete `<!DOCTYPE html>` string — modify the body content as needed.

### Changing the Stats Strip

The stats strip is at the bottom of the right column. It currently has 2 panels. To modify:
- Find the stats strip `<div>` in the HTML
- Each panel is a child `<div>` with its own content
- Adjust `grid-template-columns` if adding/removing panels

---

## Testing Changes Locally

### Quick HTML Preview

1. Create a test script that calls `buildPosterHtml()` with sample data and writes the HTML to a file:

```javascript
const { buildPosterHtml } = require('./chart-poster');

const testData = {
  branding: {
    primary_color: '#2d1b4e',
    secondary_color: '#1a1a2e',
    accent_color: '#d4af37',
    background_color: '#0f0f1a',
    text_color: '#ffffff'
  },
  tracks: [
    { rank: 1, artist: "Test Artist", title: "Test Song", plays: 50, movement: "up", delta: 2, weeks_on_chart: 3, best_rank: 1 },
    // ... add 9 more tracks
  ],
  stats: { new_entries: 2, climbers: 3, fallers: 3, non_movers: 2 },
  chart_talk: [],  // will trigger fallback generation
  show: {},
  week_display: "Week ending 3 August 2026",
  week_id: "2026-08-03",
  tagline: "The Hottest Tracks in Second Life",
  headline: "Test Headline",
  chart_story: "Test chart story narrative.",
  chart_title: "Muddy's Top 10",
  logo_url: "",
  background_url: "",
  fa_font_url: ""
};

const html = buildPosterHtml(testData);
require('fs').writeFileSync('test-output.html', html);
console.log('Written to test-output.html — open in browser');
```

2. Open `test-output.html` in a browser at 1280×720 viewport (use DevTools responsive mode).

### Full PNG Render (requires Playwright)

```bash
cd src/infographic-renderer
npm install
node -e "
  const { renderToPng } = require('./chart-poster');
  const data = { /* your test data */ };
  renderToPng(data, {}).then(buf => {
    require('fs').writeFileSync('test.png', buf);
    console.log('Rendered test.png');
  });
"
```

### Tips

- Use browser DevTools at exactly 1280×720 to preview layout accuracy.
- Base64 data URIs for logo/background/font can be empty strings during testing — the layout will render without them.
- The Chart Talk fallback logic activates automatically if `chart_talk` is empty or has fewer than 6 items — useful for testing layout without needing AI output.
- Font Awesome icons require the FA font to be loaded. Without the base64 font data, icons will appear as empty squares — this is expected in local testing.
- Changes to `chart-poster.js` require redeploying the InfographicRendererFunction Lambda. Use `sam build` + `sam deploy` or the `deploy.sh` script.
