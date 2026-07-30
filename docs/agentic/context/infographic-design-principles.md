# Design Principles for Weekly Top 10 Chart Infographics

> **Purpose**
>
> This document describes the visual system used by the existing weekly music-chart infographics so that another image-generation model can produce consistent replacements from:
>
> 1. a reference infographic;
> 2. structured weekly chart data; and
> 3. editorial notes about the week's main chart story.
>
> The reference design is a broadcast-entertainment graphic rather than a neutral data visualisation. Its job is to communicate the ranking accurately, create excitement around the countdown and remain recognisably part of the same weekly series.

---

## Target Output

* **Required dimensions:** 1280 × 720 pixels
* **Aspect ratio:** 16:9
* **Output format:** PNG
* **Colour mode:** RGB or sRGB
* **Primary uses:** Facebook, Discord, websites, radio-show promotion and archive pages
* **Minimum quality:** clean, sharp text and edges at native size
* **Preferred render method:** deterministic HTML/CSS or image generation with strict reference adherence

The supplied reference may have been generated at a larger 16:9 resolution. All measurements in this document are expressed as approximate **1280 × 720 equivalents**.

---

# 1. Visual Structure

## 1.1 Overall Layout Grid

The infographic uses a three-level structure:

```text
┌──────────────────────────────────────────────────────────────┐
│                       HEADER REGION                          │
│  Logo              Chart title/date              Tagline    │
├───────────────────────────────┬──────────────────┬───────────┤
│                               │                  │           │
│       TOP 10 CHART TABLE      │    CHART TALK    │  STATS /  │
│                               │                  │  FACT     │
│                               │                  │           │
├───────────────────────────────┴──────────────────┴───────────┤
│                       FOOTER REGION                          │
└──────────────────────────────────────────────────────────────┘
```

Approximate regions at 1280 × 720:

| Region               |          Approximate bounds |
| -------------------- | --------------------------: |
| Header               |    `x: 10–1270`, `y: 8–170` |
| Main chart table     |   `x: 12–625`, `y: 177–637` |
| Chart Talk panel     |  `x: 635–981`, `y: 177–637` |
| Chart Stats panel    | `x: 992–1268`, `y: 177–496` |
| Secondary fact panel | `x: 992–1268`, `y: 514–637` |
| Footer               |   `x: 0–1280`, `y: 647–720` |

These values are estimates and should be treated as structural proportions rather than exact pixel locks.

---

## 1.2 Horizontal Proportions

The main content area is divided approximately as follows:

```text
Chart table:        49–50%
Chart Talk:         27–28%
Stats/fact column:  21–22%
Gutters:             2–3%
```

A practical CSS grid equivalent:

```css
.main-content {
  display: grid;
  grid-template-columns:
    minmax(0, 1.75fr)
    minmax(0, 1fr)
    minmax(240px, 0.78fr);
  gap: 12px;
}
```

The chart table is deliberately the largest region because the ranking is the primary information.

---

## 1.3 Header Composition

The header has three visual anchors:

1. **Brand block at top-left**
2. **Main chart title in the centre**
3. **Tagline at top-right**

Approximate width distribution:

```text
Brand/logo:       35–37%
Chart title:      35–38%
Tagline:          24–27%
```

This creates a strong left-to-right rhythm without forcing the logo and title into direct competition.

The logo block is substantial because the venue brand is part of the graphic's identity, but the chart title remains the dominant text element.

---

## 1.4 Visual Hierarchy

The hierarchy is approximately:

1. **“TOP 10”**
2. **Muddy's logo and dog emblem**
3. **Chart rankings and artist/track names**
4. **“THIS WEEK” and date range**
5. **Chart Talk headings**
6. **Chart Stats numbers**
7. **Supporting copy**
8. **Footer promotion and social elements**

The largest object is not the number-one chart row. The title owns the top-level hierarchy, while number one is made prominent within the chart itself.

This prevents the chart table from becoming visually unbalanced.

---

## 1.5 Eye Travel and Reading Flow

The intended visual path is:

```text
Logo
  ↓
TOP 10 THIS WEEK
  ↓
Position #1
  ↓
Chart rows 2–10
  → Chart Talk
  → Chart Stats
  ↓
Footer CTA and social details
```

A more natural feed-viewing pattern is:

1. Viewer recognises the Muddy's logo.
2. Viewer reads “TOP 10 THIS WEEK.”
3. Viewer immediately checks number one.
4. Viewer scans down the ranked list.
5. Viewer glances right for the week's stories and statistics.
6. Viewer finishes at the footer branding or call to action.

This is a hybrid **Z-pattern plus vertical table scan**.

---

## 1.6 Content-to-Breathing-Room Ratio

The design is intentionally dense, but not edge-to-edge.

Approximate split:

```text
Active content and panels: 82–87%
Breathing room and gutters: 13–18%
```

Most breathing room is created through:

* internal panel padding;
* narrow gutters;
* controlled space around headings;
* dark negative space inside panels;
* spacing between Chart Talk entries.

The graphic does not use large empty regions because it must display ten tracks, commentary, statistics and branding within one 16:9 frame.

---

# 2. Consistency Mechanisms

## 2.1 Elements That Should Never Change

The following are the core brand contract:

* 16:9 landscape orientation
* exact 1280 × 720 output size
* dark navy-black background
* top-left Muddy's logo block
* central “TOP 10 THIS WEEK” title
* top-right three-line tagline
* chart table occupying the left half
* ten fixed chart rows
* Chart Talk panel in the centre-right
* Chart Stats panel at far right
* footer spanning the full width
* green rank-number column
* purple panel borders and section tabs
* white main text
* green upward movement
* red downward movement
* yellow or gold non-mover/new accents
* neon nightlife aesthetic
* rounded panel corners
* dense but regular spacing

The visual grammar should remain instantly identifiable even if all chart text is blurred.

---

## 2.2 Elements That Change Only in Content

These retain their exact structure and approximate dimensions:

* chart positions
* artist names
* track titles
* play counts
* movement values
* date range
* Chart Talk text
* Chart Stats values
* “Did You Know?” fact
* social post date or schedule text, where applicable

The rows must not reposition or resize arbitrarily based on their contents.

A new chart should feel as though the text was replaced inside the same broadcast template.

---

## 2.3 Elements That May Vary Editorially

The following may change while preserving the overall visual system:

* Chart Talk icons
* Chart Talk story order
* number of Chart Talk items, usually four to six
* supporting fact panel content
* editorial headline wording
* subtle highlight around a major statistic
* crown, star, microphone, chart, guitar or flame icons
* which movement or position receives additional emphasis
* whether the right column uses one tall stats panel or stats plus a fact panel

These changes should respond to the week's story, not to arbitrary styling preference.

---

## 2.4 Brand Recognition Without Staleness

Brand recognition comes from keeping the following fixed:

* layout
* logo
* colour palette
* title treatment
* panel shapes
* movement colours
* typography style
* footer structure

Freshness comes from varying:

* weekly stories
* supporting icons
* highlight wording
* fact content
* emphasis within Chart Talk
* small accent effects around the week's strongest story

The correct principle is:

> **Stable frame, changing editorial content.**

Do not redesign the frame each week.

---

# 3. Typography Decisions

## 3.1 Number of Type Roles

The reference effectively uses around **eight typographic roles**, though several may share the same nominal size.

Approximate 1280 × 720 sizes:

| Role                        | Approximate size |
| --------------------------- | ---------------: |
| Main “TOP 10” display title |          62–78px |
| “THIS WEEK”                 |          36–48px |
| Logo wordmark               |          48–64px |
| Date range                  |          19–24px |
| Panel headings              |          22–28px |
| Chart rank numbers          |          25–32px |
| Artist and title            |          20–25px |
| Play and movement values    |          20–26px |
| Chart Talk headline         |          16–20px |
| Chart Talk body             |          14–17px |
| Stats numeral               |          34–46px |
| Stats label                 |          14–17px |
| Footer primary text         |          15–20px |
| Footer minor text           |          13–16px |

Critical chart information should not fall below approximately **18px** at final output size.

---

## 3.2 Typography Hierarchy

The hierarchy is:

```text
Main title
↓
Section titles and major rank/stat numbers
↓
Artist and track names
↓
Movement and play values
↓
Editorial headlines
↓
Supporting copy and labels
↓
Footer metadata
```

Within chart rows:

```text
Rank number > artist/track > movement/play labels
```

The rank number is visually isolated in a coloured block, making it readable before the song name.

---

## 3.3 Font Character

The design combines:

* a bold distressed display face for “TOP 10”;
* a heavy condensed or wide sans-serif for track names;
* a clean sans-serif for small supporting copy;
* a script-style brand wordmark;
* occasional handwritten or brush styling for decorative labels.

The professional quality comes from restricting decorative typography to display roles.

Chart rows remain bold and readable.

---

## 3.4 Long Artist and Track Names

Preferred handling order:

1. Keep artist and title on one line.
2. Reduce font size slightly within a limited range.
3. Tighten letter spacing by a small amount.
4. Use a more condensed weight or face.
5. Truncate only as a last resort.

Recommended CSS:

```css
.track-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 23px;
  letter-spacing: -0.2px;
}

.track-name.long {
  font-size: 20px;
  letter-spacing: -0.5px;
}
```

Do not:

* wrap one chart row into three lines;
* shrink one track to unreadable text;
* let text collide with the Plays column;
* move the movement column to make room.

A maximum of two controlled font-size variants is preferable.

---

## 3.5 Professional vs Amateur Typography

Professional characteristics:

* no more than two functional text families plus the logo wordmark;
* strong weight contrast;
* stable font sizes across repeated elements;
* tabular or aligned numerals;
* consistent casing;
* restrained use of outlines and glows;
* adequate leading;
* deliberate letter spacing;
* no arbitrary italics or colour changes.

Amateur characteristics:

* a different font for each panel;
* every heading using a different effect;
* track names in decorative fonts;
* inconsistent font sizes row-to-row;
* excessive outlining;
* text squeezed against panel borders;
* inconsistent capitalisation;
* narrow, thin type over dark textured backgrounds.

---

# 4. Colour Strategy

## 4.1 Core Palette

The palette is built around a dark nightclub base with neon-purple and gold branding.

Approximate colours:

```css
:root {
  --bg-black:        #050510;
  --bg-navy:         #090817;
  --panel-black:     #090A16;
  --panel-purple:    #170D27;

  --text-white:      #F7F6FA;
  --text-muted:      #C6C0CC;

  --brand-purple:    #8A28D7;
  --brand-magenta:   #C52CF2;
  --brand-gold:      #F5C52D;
  --brand-yellow:    #FFDF28;

  --movement-up:     #63D83D;
  --movement-down:   #FF3636;
  --movement-same:   #F1C51C;
  --movement-new:    #2776F4;

  --rank-green:      #16B83F;
  --divider-purple:  #7C368D;
}
```

Exact colour matching is less important than preserving the roles.

---

## 4.2 Colour Roles

| Colour          | Role                                                |
| --------------- | --------------------------------------------------- |
| Near-black/navy | Canvas and panel foundation                         |
| White           | Primary information                                 |
| Purple/magenta  | Brand, headings, borders and neon effects           |
| Gold/yellow     | Major highlights, title accents, crown and emphasis |
| Green           | Positive movement and rank strip                    |
| Red             | Negative movement                                   |
| Yellow          | Non-mover or neutral movement                       |
| Blue            | New-entry or special-status icon                    |
| Grey            | Secondary labels and low-priority copy              |

---

## 4.3 Movement Recognition

Movement is encoded through three simultaneous signals:

1. **Direction or badge shape**
2. **Colour**
3. **Numeric value or status text**

Examples:

```text
↑ 8  = green upward movement
↓ 5  = red downward movement
—    = yellow or neutral non-mover
NEW  = blue or gold badge
RE   = purple or blue return badge
```

This means users can understand movement without reading the accompanying prose.

The colour must never be used without an arrow, dash or label.

---

## 4.4 Dark Background and Mood

The dark background provides:

* high contrast for white text;
* a nightclub and broadcast atmosphere;
* visual depth;
* room for neon and glowing accents;
* stronger feed visibility than a neutral white layout;
* a premium entertainment rather than spreadsheet appearance.

The black is rarely pure black. Subtle purple or blue gradients prevent the canvas from appearing flat.

---

## 4.5 Weekly Story Accents

Gold or bright yellow is used for important weekly narratives:

* retained number one;
* crown story;
* major headline;
* special artist achievement;
* title accents.

Green is used when the story is about momentum or a climber.

Purple and magenta are used for branded framing rather than data meaning.

Red should normally be reserved for negative movement, preventing semantic confusion.

---

# 5. Data Visualisation Choices

## 5.1 Primary and Secondary Information

### Primary

* rank
* artist
* track title
* movement
* number-one result

### Secondary

* play count
* summary statistics
* major chart stories
* fact or trivia
* show CTA

### Tertiary

* social handles
* promotional footer wording
* decorative icons

The chart table should remain readable even if the right-hand panels are ignored.

---

## 5.2 Chart Row Information

The reference uses:

```text
Rank | Artist – Track | Plays | Movement
```

This is sufficient to explain the result without making the table feel like an analytics dashboard.

The movement column is intentionally compact and aligned.

---

## 5.3 Movement at a Glance

Movement values are isolated in the far-right chart column.

This creates a vertical visual scan:

```text
—
↑2
↑2
↑2
↑2
↑8
↓5
—
↑39
↑3
```

Even before reading artist names, the viewer can see that the week was upward-moving overall.

This is an important design success: the chart's overall volatility is visible as a pattern.

---

## 5.4 Supporting Statistics

Useful statistics include:

* number moving up
* number moving down
* number of non-movers
* new entries
* re-entries
* biggest climber
* new number one
* multiple entries by one artist

Supporting stats should summarise the chart, not duplicate it.

Avoid:

* total plays unless editorially meaningful;
* median movement;
* average weeks on chart;
* percentage of artists by category;
* excessive numeric analysis;
* facts already obvious from the table.

Three or four summary statistics are usually enough.

---

## 5.5 Chart Talk Panel

The Chart Talk panel converts raw data into a weekly narrative.

Each story is formed from:

```text
Icon + short headline + one-sentence explanation
```

Example pattern:

```text
[Crown icon]
Ella Langley holds the crown!
Choosin' Texas stays #1 for another week.
```

The headline carries emotional framing.

The second line provides evidence.

This panel should normally contain:

* one number-one story;
* one major movement story;
* one artist achievement;
* one broader chart trend;
* optionally one return or new-entry story.

The stories should be ordered by editorial importance, not chart position.

---

## 5.6 Visual Storytelling

The week's primary story is highlighted through:

* top placement in Chart Talk;
* a distinctive icon;
* gold headline text;
* concise wording;
* stronger contrast;
* sometimes a crown or star.

The table remains factual.

The Chart Talk panel interprets the facts.

This separation allows the graphic to be both informative and entertaining.

---

# 6. What Makes It Look Professional

## 6.1 Broadcast-Like Qualities

The graphic resembles a published broadcast asset because it has:

* a fixed branded header;
* a repeatable chart table;
* strong programme title treatment;
* clear content regions;
* a disciplined colour system;
* movement semantics;
* editorial commentary;
* visible scheduling and social promotion;
* consistent borders and dividers;
* a polished entertainment aesthetic.

It looks like part of a programme package, not a standalone chart made in a spreadsheet.

---

## 6.2 Alignment Patterns

Important alignment rules:

* all rank blocks share identical width;
* all chart rows share equal height;
* all artist/title labels start at the same x-coordinate;
* all play values share one centre line;
* all movement values share one centre line;
* Chart Talk icons share one vertical axis;
* Chart Talk text shares one left edge;
* right-column statistics use repeating icon-number-label structures;
* footer items align to one vertical centre.

Even highly decorative visuals appear professional when their underlying alignment is strict.

---

## 6.3 Spacing System

Approximate 1280 × 720 values:

```text
Outer canvas margin:          8–16px
Major panel gap:             10–14px
Panel internal padding:      14–18px
Chart row horizontal pad:    10–14px
Chart row height:            43–47px
Chart Talk item height:      63–72px
Footer internal pad:         12–18px
```

Use a spacing system based around:

```text
4px, 8px, 12px, 16px, 24px, 32px
```

Do not introduce arbitrary spacing per element.

---

## 6.4 Borders and Dividers

Panels use:

* thin purple or pale-lilac outlines;
* rounded corners;
* subtle external glow;
* dark internal fill.

Chart rows use:

* horizontal separators;
* fixed column dividers;
* no large spacing gaps.

The borders create the structure of a broadcast control panel or digital scoreboard.

Recommended:

```css
.panel {
  border: 1.5px solid rgba(205, 119, 255, 0.78);
  border-radius: 12px;
  box-shadow:
    0 0 12px rgba(163, 51, 255, 0.20),
    inset 0 0 18px rgba(94, 31, 145, 0.10);
}
```

Borders should define structure without overpowering the content.

---

## 6.5 Nightclub and Music-Venue Aesthetic

The aesthetic comes from the combined use of:

* near-black background;
* purple and magenta neon;
* gold marquee accents;
* illuminated signage;
* brush-stroke section headers;
* “LIVE” and “ON AIR” elements;
* microphone and music icons;
* subtle glows;
* large distressed title lettering;
* compact, energetic chart presentation.

No single effect creates the look.

It is the combination of broadcast signage and nightlife colour.

---

# 7. Variation Strategy

## 7.1 Choosing the Weekly Feature

Priority order for editorial emphasis:

1. New number one
2. Number one extending a notable run
3. Very large climber
4. Major re-entry
5. Multiple songs by one artist
6. High new entry
7. New peak inside the Top 3
8. Returning classic
9. Longest-running track
10. Overall chart trend

Minor two-place movements should not displace a major number-one story.

---

## 7.2 When the Chart Is Quiet

A static chart can still produce useful stories through:

* consecutive weeks at number one;
* chart longevity;
* songs holding their peaks;
* narrow play-count margins;
* sustained listener support;
* an artist with multiple positions;
* a classic remaining popular;
* anticipation about what may change next week.

Visual treatment should remain energetic, but the wording should not manufacture false drama.

Example:

> **Still holding strong**
> Seven of this week's Top 10 retain places in the upper half of the chart.

Do not label a one-place rise as “rocketing.”

---

## 7.3 When There Is a Major Story

For a new number one or exceptional movement:

* place it first in Chart Talk;
* use a crown, upward chart or spotlight icon;
* use gold for a new number one;
* use bright green for a major climber;
* make the headline slightly larger or bolder;
* give the story more vertical space if necessary;
* reduce a lower-priority story rather than overcrowding the panel.

Within the table, extra emphasis may include:

* gold border on the number-one row;
* crown icon beside rank one;
* subtle glow;
* stronger row background.

Do not radically redesign the entire chart.

---

## 7.4 Acceptable Variation

Acceptable:

* different Chart Talk icon selection;
* changing the supporting fact;
* changing one accent highlight;
* emphasising a specific row;
* using four stories instead of five;
* replacing “Did You Know?” with “Biggest Climber”;
* adding a crown for a new number one;
* highlighting a major re-entry.

---

## 7.5 Variation That Breaks the Brand

Unacceptable:

* moving the chart table to the right;
* changing the background to white;
* removing the purple border system;
* changing green to mean down;
* using a different layout each week;
* changing all typefaces;
* altering the logo placement;
* replacing the title hierarchy;
* using photographs as a full background;
* turning the chart into ten unrelated cards;
* changing from dark nightlife styling to pastel minimalism;
* letting editorial art obscure chart data.

The boundary is:

> Content emphasis may vary; structural identity must not.

---

# 8. Reference Image Contract

## 8.1 Model Input Assumptions

The model receives:

* one reference image;
* structured chart data;
* date range;
* Chart Talk stories;
* Chart Stats values;
* optional weekly fact;
* optional editorial priority.

The reference image defines the visual template.

The structured data defines the new content.

The model must not treat the reference as a loose mood board.

---

## 8.2 What Must Be Preserved

Preserve as closely as possible:

* 16:9 composition;
* 1280 × 720 output;
* dark navy-black background;
* top-left logo position and relative scale;
* central title position;
* top-right tagline;
* main chart table position and size;
* all ten row positions;
* Plays and Movement columns;
* Chart Talk panel;
* Chart Stats panel;
* optional fact panel;
* footer position and height;
* green rank strip;
* purple borders;
* gold and purple brand accents;
* white chart text;
* green/red/yellow movement semantics;
* rounded corners;
* neon/broadcast aesthetic;
* typography hierarchy;
* overall data density;
* reading flow.

The generated image should look like the next edition of the same series.

---

## 8.3 What May Be Adapted

The model may adapt:

* text content;
* row font size within approved limits;
* number of Chart Talk items;
* icon choice from the established visual family;
* featured weekly story;
* supporting statistics;
* fact panel content;
* subtle highlight intensity;
* row emphasis for number one or a major climber;
* line breaks inside supporting commentary;
* minor spacing to accommodate content.

Adaptation should solve content-fit problems without altering the underlying grid.

---

## 8.4 Required Data Accuracy

The model must:

* include all ten positions exactly once;
* preserve the provided ranking order;
* copy artist and title spelling exactly;
* copy play counts exactly;
* calculate or display movement correctly;
* distinguish non-movers from new entries;
* not invent new entries or re-entries;
* keep Chart Stats mathematically consistent with the rows;
* not include total plays unless requested;
* ensure Chart Talk statements agree with the data;
* use the correct date range;
* avoid changing factual names through stylisation.

The model must prioritise text accuracy above decorative quality.

---

## 8.5 Text Handling Rules

* Never allow chart text to overlap adjacent columns.
* Never let artist/title text cross into Plays or Movement.
* Use one line per chart row.
* Apply controlled font scaling for long names.
* Truncate only when explicitly permitted.
* Do not break an artist's name from the song title in a way that obscures attribution.
* Preserve official title casing where supplied.
* Use consistent alignment for numbers.
* Keep critical text sharp and readable.

Where an image-generation model cannot reliably render exact text, the preferred workflow is:

```text
Generate decorative background and panels
↓
Overlay all chart text through HTML/CSS or SVG
↓
Render final PNG
```

A pure image-generation workflow carries substantial spelling and alignment risk.

---

## 8.6 Failure Modes

### Data failures

* missing chart position;
* duplicate position;
* wrong artist or track;
* reordered chart;
* wrong movement direction;
* movement value copied into the wrong row;
* stats not matching the chart;
* invented play counts;
* incorrect number one.

### Layout failures

* chart rows changing height unpredictably;
* long text overlapping;
* rank numbers outside blocks;
* columns no longer aligned;
* Chart Talk overflowing its panel;
* footer being cut off;
* title colliding with logo or tagline;
* right-side panels extending beyond the canvas.

### Brand failures

* changing the primary palette;
* moving the logo;
* changing movement colours;
* using unrelated icon styles;
* replacing the nightlife aesthetic;
* removing the panel system;
* inconsistent typography;
* overusing gradients or glows.

### Rendering failures

* blurry text;
* malformed letters;
* missing punctuation;
* warped logos;
* unreadable small text;
* inconsistent borders;
* low-resolution output;
* compression artefacts;
* partial cropping;
* accidental transparency.

---

## 8.7 Resolution and Quality Expectations

Final output must be:

```text
1280 × 720 pixels
PNG
sRGB
No transparency unless explicitly required
No crop
No watermark
No additional margins
```

Recommended raster quality:

* sharp text edges;
* antialiased shapes;
* no visible JPEG artefacts;
* no artificial film grain over text;
* no generative smearing;
* no partially formed letters;
* no icon deformation.

The graphic should remain structurally clear at:

```text
640 × 360
```

and retain its basic hierarchy at:

```text
320 × 180
```

At thumbnail size, viewers should still recognise:

* the Muddy's brand;
* “TOP 10”;
* the ranking-table form;
* the number-one entry;
* the purple/gold/green colour system.

---

# Recommended Structured Input

```json
{
  "chart_period": "18–25 July 2026",
  "entries": [
    {
      "rank": 1,
      "artist": "Ella Langley",
      "title": "Choosin' Texas",
      "plays": 24,
      "movement_type": "same",
      "movement_value": 0
    }
  ],
  "stats": {
    "moving_up": 7,
    "moving_down": 1,
    "non_movers": 2,
    "new_entries": 0,
    "re_entries": 0
  },
  "chart_talk": [
    {
      "type": "number_one",
      "headline": "Ella Langley holds the crown!",
      "body": "Choosin' Texas stays #1 for another week."
    }
  ],
  "fact": {
    "heading": "Did You Know?",
    "body": "Optional short supporting fact."
  },
  "editorial_priority": "retained_number_one"
}
```

---

# Image-Generation Instruction Template

```text
Use the supplied Top 10 infographic as a strict visual template, not merely
as stylistic inspiration.

Produce a 1280×720 PNG that appears to be the next weekly edition of the
same chart series.

Preserve the reference image's overall grid, logo placement, chart-table
dimensions, ten-row structure, Chart Talk panel, Chart Stats panel, footer,
dark nightclub background, purple neon borders, gold brand accents, green
rank column and movement colour semantics.

Replace only the variable weekly content using the supplied structured data.

All ten chart rows must retain identical height and column alignment. Artist
and track names must remain on one line and must not overlap the Plays or
Movement columns. Reduce the chart-row font slightly for unusually long names
rather than changing the row structure.

Use green upward arrows for climbers, red downward arrows for fallers, a
yellow dash for non-movers, a gold or blue NEW treatment for new entries and
a purple or blue RE treatment for re-entries.

Use the Chart Talk panel to feature the week's most important stories in
editorial priority order. Use short headlines followed by one concise
supporting sentence. Emphasise the principal story with a crown, star or
chart icon and a gold or green accent, depending on the story type.

Do not invent, omit, reorder or rewrite chart data. Chart statistics must
mathematically match the ten supplied rows.

Do not alter the established brand layout, colours, panel system, logo scale,
typography hierarchy or footer position. Do not add unrelated decorations,
photographs or new sections.

Render all text sharply and legibly. Check for overlap, malformed lettering,
cropping, incorrect movement colours, duplicate positions and missing chart
entries before final output.
```

---

# Final Quality Checklist

Before accepting a generated infographic, verify:

## Structure

* [ ] Exactly 1280 × 720
* [ ] Correct 16:9 layout
* [ ] Logo remains top-left
* [ ] Chart title remains top-centre
* [ ] Tagline remains top-right
* [ ] Chart occupies the left half
* [ ] Chart Talk occupies the centre-right
* [ ] Stats/fact column remains far right
* [ ] Footer spans the full width

## Data

* [ ] All ten positions are present
* [ ] Ranking order is correct
* [ ] Artist names are correct
* [ ] Track titles are correct
* [ ] Play counts are correct
* [ ] Movement values and directions are correct
* [ ] Stats reconcile with the rows
* [ ] Chart Talk claims are factually supported

## Typography

* [ ] No overlapping text
* [ ] Long names remain readable
* [ ] No malformed letters
* [ ] No inconsistent font size without reason
* [ ] Numeric columns align
* [ ] Body copy is not too small

## Brand

* [ ] Dark background retained
* [ ] Purple neon system retained
* [ ] Gold highlights retained
* [ ] Green means up
* [ ] Red means down
* [ ] Non-movers use the approved neutral treatment
* [ ] Rounded panel system retained
* [ ] Nightclub/broadcast aesthetic retained

## Editorial

* [ ] The week's most important story is featured first
* [ ] Secondary stories are genuinely useful
* [ ] No exaggerated claims
* [ ] Supporting facts do not clutter the graphic
* [ ] Variation feels fresh without changing the template

---

## Core Principle

> The infographic works because it combines the accuracy and repeatability of a chart table with the excitement and identity of a live entertainment brand.
>
> Keep the structure stable, keep the data exact, and let only the week's story change.
