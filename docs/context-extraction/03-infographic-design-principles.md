# Prompt: Infographic Design Principles

**Target file:** `docs/agentic/context/infographic-design-principles.md`

---

## Paste this into ChatGPT:

```
I'm building an AI system that generates weekly music chart infographics (1280×720 PNG images). The AI needs to understand visual design principles specific to chart/ranking infographics so it can author professional HTML/CSS layouts.

Please write a reference document covering:

## 1. Visual Hierarchy for Rankings
- How to make #1 visually dominant without overwhelming the layout
- Graduated emphasis (top positions get more visual weight)
- How movement indicators (up/down/new/same) should be sized and positioned
- Balance between data density and readability at the target resolution

## 2. Typography for Chart Graphics
- Font pairing principles (display vs body, condensed for data-heavy layouts)
- Sizing hierarchy: title > subtitle > position numbers > track names > metadata
- How to handle long track names and artist names (truncation vs wrapping vs font scaling)
- Readable font sizes at 1280×720 (minimum sizes that work when shared on social media)
- When to use uppercase vs title case vs sentence case

## 3. Colour Usage in Music/Entertainment Graphics
- Dark backgrounds for impact and social media visibility
- Accent colours for movement indicators (standard conventions: green=up, red=down, yellow/gold=new, grey=same)
- How to use a limited palette (5-6 colours max) effectively
- Contrast ratios for accessibility on social media
- Neon/vibrant palettes for nightlife/music contexts
- How colour temperature creates mood (warm=energy, cool=sophistication)

## 4. Layout Principles for 16:9 Chart Graphics
- Grid-based composition for 1280×720
- Safe zones (social media crops differently per platform)
- How to structure: header region, main chart area, supporting stats, footer/promotion
- White space management when displaying 10 ranked items
- Where to place branding elements (logo, tagline) without competing with content

## 5. Information Design for Charts
- What metadata to show per track (rank, artist, title, play count, movement, weeks on chart)
- What to omit (too much data = noise)
- Supporting statistics that add context (total plays, new entries count, biggest climber)
- "Chart story" as a visual callout (1-2 sentences highlighting the week's narrative)
- How movement arrows/icons communicate at a glance

## 6. Social Media Optimisation
- How these graphics appear in feeds (Facebook preview crops, Discord embeds, mobile vs desktop)
- Text legibility at thumbnail size
- Why bold contrast matters more than subtlety for social sharing
- Aspect ratio considerations (1280×720 is 16:9 — good for Discord/Twitter, acceptable for Facebook, not ideal for Instagram stories)

## 7. Professional vs Amateur Tells
- What makes a chart graphic look professional (consistent spacing, alignment, intentional hierarchy)
- Common mistakes (too many fonts, inconsistent spacing, poor contrast, cluttered layout)
- How consistency week-to-week builds brand recognition
- When variation is good (content emphasis) vs bad (inconsistent structure)

Write this as a reference document an AI will use when authoring HTML/CSS for chart infographics. Focus on actionable principles, not theory. Use specific measurements, ratios, and examples where possible. Markdown format.
```

---

## Notes

- Domain knowledge about visual design, not Muddy's-specific branding.
- The Muddy's branding (colours, logo, tagline) is already defined in config — this doc teaches the agent *how* to use design elements effectively.
- Particularly important for the model-authored infographic HTML/CSS path which currently struggles with layout quality.
