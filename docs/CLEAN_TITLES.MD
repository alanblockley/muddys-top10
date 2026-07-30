# Title Cleaning Patterns

Clean song and artist metadata by removing DJ pool tags, quality markers, and normalizing formatting. This is the **first step** in the track processing pipeline - after cleaning, tracks are validated against music databases to get canonical names.

## Pipeline

```
Raw Shoutcast metadata
  → Clean with CLEAN_TITLES.MD rules (this file)
  → Save to DynamoDB
  → Validate against MusicBrainz/Spotify (see TRACK_VALIDATION.md)
  → Store canonical name
```

The goal of cleaning is to produce readable track information suitable for validation. The validation step then corrects typos and normalizes artist/title formatting.

## Song Name Cleaning

### Remove Pool/Source Tags
Remove these bracketed tags (case-insensitive):
- `[Xtendz]`
- `[Single]`
- `[Club]`
- `[DMS]`
- `[Funkymix]`
- `[BlenX]`
- `[Ultimix]`
- `[DJ Re-Grid]`

### Remove Quality/Format Suffixes
Remove these trailing markers:
- `- Clean`
- `- Dirty`
- `- HD`
- `- qHD`
- `- 1080`
- `- HD - Clean`
- `- HD - Dirty`
- `- qHD - Clean`
- `- qHD - Dirty`
- `- 1080 - Clean`
- `(Clean)`
- `(Dirty)`
- `(Explicit Edit)`
- `(Explicit Version)`

### Remove DJ/Radio Markers
- `(Lyric Video)`
- `(Radio)` with optional trailing number
- `(DJ Beats)` with optional count in parentheses
- BPM transition markers: `[128-70]`, `(Transition 128-70)`, `(128~70)`
- Trailing BPM numbers in parentheses: `(125)`
- Trailing BPM numbers: 100-200 only (preserves numbers that are part of the title)

### Remove Remix/Version Information
Remove parentheses at end of song containing any of these words:
- Remix
- Mix
- Edit
- Version
- Bootleg
- Mashup
- Remaster

Example: `Song Name (Club Remix)` becomes `Song Name`

### Remove Trailing Bracket Content
Remove content in square brackets at end of song, unless the brackets contain URLs (preserve URLs for advertising purposes).

## Artist Name Cleaning

### Remove Leading Track Numbers
Strip leading track numbers like `001. `, `03. `, `10. ` from artist names.

### Normalize Featuring Credits
Convert all featuring variations to `ft.`:
- `feat.` / `feat`
- `featuring`
- `ft.` / `ft`
- `Feat.` / `Feat`
- `Featuring`
- `FT.` / `FT`

Example: `Artist featuring Other Artist` becomes `Artist ft. Other Artist`

### Normalize "n" to Ampersand
Convert standalone `n` (used as "and") between artists to `&`:

Example: `Calvin Harris n Dua Lipa` becomes `Calvin Harris & Dua Lipa`

## Trailing Number Handling

Only removes numbers in the typical BPM range (100-200) to avoid removing numbers that are part of the song title.

### Removed (BPM metadata)
- `Artist - Song 128` → `Artist - Song`
- `Artist - Track 125` → `Artist - Track`
- `Artist - Title 150` → `Artist - Title`
- `Artist - Mix 100` → `Artist - Mix`
- `Artist - Beat 200` → `Artist - Beat`

### Preserved (part of title)
- `Sombr - 12 To 12` → `Sombr - 12 To 12` (small number)
- `Artist - 24 Hours` → `Artist - 24 Hours` (small number)
- `Artist - Track 1` → `Artist - Track 1` (small number)
- `Artist - 99 Problems` → `Artist - 99 Problems` (below BPM range)
- `Artist - 3AM` → `Artist - 3AM` (small number)
- `Artist - Year 2024` → `Artist - Year 2024` (above BPM range)

## Promotional Entry Bypass

Pass these entries through without any cleaning:
- Artists starting with `Muddy's` or `Muddys` (e.g., "Muddy's Music Cafe", "Muddys Roadshow")
- Artists starting with `MUDDY` (e.g., "MUDDY's - DJ OLIVER on MIC")
- Artists starting with `Send your` (dedication messages)
- Artists that are URLs (starting with `http://` or `https://`)
- Content containing SecondLife URLs (`secondlife:///`)

## General Rules

- All pattern matching is case-insensitive
- Collapse multiple spaces to single space
- Trim leading/trailing whitespace from final output
- Preserve URLs in song content (for Shoutcast advertising)
