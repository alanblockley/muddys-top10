# Infographic Editorial Framework

This document defines the editorial specification for the Chart Talk section of the Muddy's Top 10 infographic. Chart Talk transforms a list of songs into a narrative — telling the story of why this week's chart is interesting.

## The Content Model

The infographic contains three layers:

1. **Facts (deterministic)** — ranking, artist, song, plays, movement, stats. Generated from chart_brief. Never AI-written.
2. **Editorial (AI-generated)** — the Chart Talk cells. What made THIS week unique. This is where the AI adds value.
3. **Layout (fixed template)** — visual design, grid, colours. Never changes week-to-week.

## Chart Talk Cells

The infographic has 6 Chart Talk cells in a 2×3 grid. Each cell contains:
- An icon (Font Awesome class, decorative)
- A headline (5-15 words, energetic, radio-friendly)
- A body (1-2 short sentences explaining the story)

The AI generates these 6 cells each week by selecting from the editorial categories below based on what's interesting in the current chart data.

## Editorial Categories (pick 6 per week)

### Priority ⭐⭐⭐⭐⭐ (always include if applicable)

**Chart Leader** — What's notable about #1?
- First ever #1, consecutive weeks, new leader, returned to #1, record play count, narrow victory
- Example headline: "HOLDS THE CROWN!" / "NEW NUMBER ONE!" / "THREE WEEKS RUNNING!"

**Biggest Climber** — Largest upward move.
- Example headline: "ROCKETS UP 14!" / "BIGGEST MOVER!" / "THUNDERSTRUCK!"

### Priority ⭐⭐⭐⭐

**New Entry / Return** — Fresh arrival or comeback.
- Highest debut, returning artist, returning classic
- Example headline: "WELCOME BACK!" / "STRAIGHT IN!" / "NEW ENERGY!"

**Long Run** — Weeks in chart or consecutive weeks at #1.
- Example headline: "10 WEEKS AND COUNTING!" / "LONG RUN LEGEND!"

### Priority ⭐⭐⭐

**Equal Plays / Tied Positions** — Explains rankings vs play counts.
- Example headline: "DOUBLE TROUBLE!" / "TOO CLOSE TO CALL!"

**Multiple Songs by One Artist** — Same artist places multiple tracks.
- Example headline: "DOUBLE THREAT!" / "OWNS THE CHART!"

**Interesting Statistics** — Total plays, unique artists, chart age.
- Example headline: "BY THE NUMBERS" / "141 PLAYS THIS WEEK"

### Priority ⭐⭐

**Biggest Faller** — If it's a meaningful story (not just normal fluctuation).
- Example headline: "GIVES UP GROUND" / "SLIPS BACK"

**Narrative Momentum** — Artists on a streak or steady climb.
- Example headline: "KEEPS CLIMBING!" / "UPWARD MOMENTUM!"

**Non-Movers** — Songs holding steady, stability story.
- Example headline: "HOLDS STEADY!" / "NOT BUDGING!"

### Priority ⭐

**Returning Track** — Older song reappears.
- Example headline: "MADONNA MAGIC!" / "BACK FROM '90!"

**Fun Fact / Trivia** — A talking point when relevant.
- Example headline: "DID YOU KNOW?" / "CHART HISTORY!"

## Selection Rules

1. Always lead with the #1 story and biggest climber (cells 1-2)
2. Fill cells 3-6 from the remaining categories in priority order
3. Only include a category if the data supports it — never invent
4. Prefer stories that explain what listeners CAN'T see from the chart alone
5. If the chart is stable (few movements), lean into longevity and momentum stories
6. If the chart is volatile, lean into movement and new entries
7. **No artist may appear in more than one Chart Talk cell** — each cell must feature a different artist or topic
8. All 6 cells must contain genuine editorial content — never use filler like the chart name or tagline

## Tone Rules

- Headlines: 5-15 words, ALL CAPS, energetic, punchy
- Body: 1-2 sentences, conversational, radio-friendly
- Never negative — frame falls as "gives up ground" not "crashed and burned"
- Never overhyped — "climbs 3 places" not "INCREDIBLE UNSTOPPABLE RISE"
- Written so a DJ can glance at it and use the language on-air
- Chart Talk is NOT a radio read — it's a visual one-liner for quick scanning

## Constraints

- Headline: maximum 25 characters
- Body: maximum 90 characters
- Icon: a Font Awesome icon class name (e.g., fa-trophy, fa-rocket, fa-star, fa-music, fa-fire, fa-arrow-up, fa-chart-line)
- The AI must self-verify that text fits within these limits before returning

## Available Data Per Track (use for richness)

Each track in chart_brief includes:
- `rank` — current position
- `play_count` — plays this week
- `movement` — up/down/new/same/reentry
- `movement_delta` — positions gained/lost
- `previous_rank` — last week's position
- `weeks_on_chart` — total weeks this track has appeared
- `best_rank` — highest position ever achieved
- `last_seen_week` — for re-entries, when it was last charted

Use these to write richer editorial:
- "Now in its 8th week on the chart" (weeks_on_chart)
- "Reaches a new peak at #3" (rank < best_rank means new peak)
- "Returns after dropping out 4 weeks ago" (last_seen_week)
- "Still below its peak of #1" (best_rank vs current rank)
- Don't just state movement — explain what it MEANS for the artist

## All 6 Cells Must Be Track-Specific

Every Chart Talk cell must be about a specific artist and their story this week. No chart summarisations, no generic statements, no filler. Each cell = one artist = one story.

## Output Format

The AI should return `chart_talk` as an array of exactly 6 objects:

```json
[
  { "icon": "fa-trophy", "headline": "NEW NUMBER ONE!", "body": "Olivia Dean takes the crown after climbing 3 places." },
  { "icon": "fa-rocket", "headline": "BIGGEST CLIMBER!", "body": "Sabrina Carpenter rockets up 4 places to #8." },
  ...
]
```
