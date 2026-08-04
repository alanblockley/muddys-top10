# Context Extraction Prompts

This directory contains ChatGPT prompts designed to extract the knowledge needed to populate the campaign generation context files.

## Why This Exists

The campaign agents need two layers of knowledge to produce professional output:

1. **Domain knowledge** — how radio chart shows work, infographic design principles, social media for music communities. This is universal genre knowledge, not specific to Muddy's.
2. **Personalisation** — DJ Toohey's voice, Muddy's community culture, specific preferred/banned phrases. This is unique to this show.

Without both layers, the agents produce generic content that needs heavy manual editing — defeating the purpose of automation.

## Context File Inventory

### Domain Knowledge (new files to create)

| File | Purpose | Prompt |
|------|---------|--------|
| `docs/agentic/context/radio-chart-show-convention.md` | How professional radio chart countdowns work — structure, pacing, tension, reveal patterns | [01-radio-chart-conventions.md](01-radio-chart-conventions.md) ✅ ALREADY POPULATED |
| `docs/agentic/context/chart-show-glossary.md` | Industry terminology for chart shows and radio broadcasting | [02-chart-show-glossary.md](02-chart-show-glossary.md) |
| `docs/agentic/context/infographic-design-principles.md` | Visual design principles for music chart infographics | [03-infographic-design-principles.md](03-infographic-design-principles.md) |
| `docs/agentic/context/social-media-music-communities.md` | How music communities engage on social media, what drives shares/engagement | [04-social-media-music-communities.md](04-social-media-music-communities.md) |

### Personalisation (existing placeholders to populate)

| File | Purpose | Prompt |
|------|---------|--------|
| `docs/agentic/context/personal-voice.md` | Alan's writing voice — tone, humour, directness, natural phrases | [05-personal-voice.md](05-personal-voice.md) |
| `docs/agentic/context/muddys-venue-context.md` | Muddy's Music Cafe — what it is, community, culture, Second Life context | [07-muddys-venue-context.md](07-muddys-venue-context.md) |
| `docs/agentic/context/radio-read-examples.md` | Golden examples of radio reads that sound right | [08-radio-read-examples.md](08-radio-read-examples.md) |
| `docs/agentic/context/infographic-style-examples.md` | Infographic copy direction — headlines, chart story, movement language | [09-infographic-style-examples.md](09-infographic-style-examples.md) |
| `docs/agentic/context/social-style-examples.md` | Social post examples that sound right for each platform | [10-social-style-examples.md](10-social-style-examples.md) |
| `docs/agentic/context/words-and-phrases.md` | Preferred vocabulary grouped by output type | [11-words-and-phrases.md](11-words-and-phrases.md) |
| `docs/agentic/context/never-say.md` | Banned words, phrases, claims, framing | [12-never-say.md](12-never-say.md) |

## How to Use

1. Open each numbered prompt file in this directory.
2. Paste the prompt into ChatGPT (GPT-4 recommended — it has the domain knowledge from training).
3. Review the output, edit for accuracy, and paste into the target context file.
4. Some prompts (05–12) require *your* input — they'll ask you questions or need examples from past shows.

## Order Matters

Do domain knowledge first (01–04) since those don't require personal input. Then do personalisation (05–12) which needs your voice, examples, and preferences.

## After Populating

Once all files are populated, the campaign agents will load them via `agent_context.py` and include them in generation prompts. No code changes needed — the file paths are already wired up.
