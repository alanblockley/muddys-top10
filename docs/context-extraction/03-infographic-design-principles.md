# Prompt: Infographic Design Principles

**Target file:** `docs/agentic/context/infographic-design-principles.md`

---

## Context for You (Alan)

The current system has two infographic paths:
1. **Image generation** (preferred) — model sees a reference PNG + chart data → produces a new PNG
2. **HTML/CSS + Playwright** (fallback) — model writes code → headless browser renders it

When you made infographics with ChatGPT, you were using the image generation approach (either explicitly or through GPT-4o's multimodal capabilities). That's why they were consistent — the model was *seeing* the reference and reproducing the visual style while changing the data.

This prompt extracts what ChatGPT was doing right so the automated system can replicate it.

---

## Paste this into ChatGPT:

```
I've been using you (ChatGPT) to create weekly music chart infographics for my Top 10 show. They've been consistently professional-looking and on-brand. I'm now automating this with an AI system that will use image generation (a model sees a reference PNG + structured chart data and produces a new PNG).

I need you to help me document WHY the infographics you've been creating work — the design principles you've been applying — so I can give that knowledge to another model as context.

[ATTACH 2-3 OF YOUR BEST INFOGRAPHIC PNGS FROM samples/ HERE]

Looking at the infographics you've created for me, please analyse and document:

## 1. Visual Structure
- What's the layout grid? (Where are the major regions positioned?)
- How is visual hierarchy established? (What's biggest/most prominent → smallest)
- How does the eye travel across the image? (Reading flow)
- What's the ratio of content area to whitespace/breathing room?

## 2. Consistency Mechanisms
- What elements NEVER change week-to-week? (Logo position, background, structural panels)
- What elements change ONLY in content? (Chart rows — same size/position, different text)
- What elements can vary for editorial emphasis? (Chart Talk, callouts, featured story)
- How do you maintain brand recognition across weeks while avoiding staleness?

## 3. Typography Decisions
- How many font sizes are in play? List them by role.
- What's the hierarchy? (Title > position numbers > artist names > metadata > labels)
- How do you handle long artist/track names without breaking the layout?
- What creates the "professional" feel vs "amateur" feel in type choices?

## 4. Colour Strategy
- What's the colour palette and what role does each colour play?
- How do movement indicators use colour for instant recognition?
- How does the dark background create contrast and mood?
- What colour accents draw attention to the week's story?

## 5. Data Visualisation Choices
- How do you decide what to emphasise vs what's secondary?
- How do movement indicators communicate at a glance (without reading)?
- What supporting stats add context vs which would be clutter?
- How does the "Chart Talk" section tell the week's story visually?

## 6. What Makes It Look Professional
- What specific things make this look like a published broadcast graphic vs a hobbyist creation?
- Spacing, alignment, and consistency patterns you're applying
- How do panel borders/dividers create structure?
- What gives it the "nightclub / music venue" aesthetic?

## 7. Variation Strategy
- How do you decide what to feature differently each week?
- When the chart is boring (few movements), how do you keep the graphic interesting?
- When there's a big story (new #1, dramatic movement), how do you visually emphasise it?
- What's the boundary between "acceptable variation" and "broke the brand"?

## 8. Reference Image Contract
If another AI model receives one of these infographics as a "reference image" along with new chart data, what instructions would you give it to produce a consistent output?
- What must it preserve exactly?
- What can it adapt?
- What are the failure modes to watch for? (text overlapping, wrong colours, missing elements)
- What resolution/quality expectations apply?

Format this as a design principles document in markdown. Be specific — include pixel estimates, colour hex values, font size relationships, spacing ratios where you can infer them from the reference. This will be used as context for an AI generating new infographics each week.
```

---

## Notes

- **Upload your best infographic PNGs** from `samples/` when running this prompt — ChatGPT needs to see them to analyse its own design decisions.
- This replaces the HTML/CSS-focused approach with understanding the *visual intelligence* that made the manual process work.
- The output feeds into the image generation prompt, not a code renderer.
- If the image generation path works well with this context, the HTML/CSS fallback becomes a safety net rather than the primary mechanism.
- You may want to run this twice — once analysing your reference images, once asking "if you had to recreate this from data alone, what would you need to know?"
