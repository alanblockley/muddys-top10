# Track Validation and Canonicalisation Logic

## Purpose

Create a component that accepts a raw music string from a user, attempts to determine whether it represents a valid track, and returns the most likely canonical or official representation.

This is not just a search. The goal is to:
- validate whether the input appears to map to a real track
- correct obvious typos
- separate artist, title, and extra contextual noise
- return a normalised result suitable for storage, display, or downstream matching

Example input:

`HUNTRIX - What It Sounds Like KPop Demon Hunters`

Expected outcome:

- artist: `HUNTR/X`
- title: `What It Sounds Like`
- optional extended title: `What It Sounds Like (from the Netflix film KPop Demon Hunters)`

---

## High-Level Flow

```text
Raw input
  -> preprocess and normalise
  -> attempt to parse into artist/title/context
  -> generate search candidates
  -> query metadata source(s)
  -> score and rank candidate matches
  -> decide whether match confidence is strong enough
  -> return canonical result + corrections + confidence
```

---

## Recommended Source Strategy

Use a layered approach:

1. **Primary canonical source**
   - MusicBrainz
   - Good for open metadata, stable IDs, canonical names

2. **Secondary mainstream coverage**
   - Spotify or similar modern catalogue source
   - Good for newer or popular tracks and current artist styling

3. **Optional enrichment**
   - Discogs for version and release detail
   - Last.fm for loose tag support only, not canonical truth

Suggested rule:
- Treat MusicBrainz as the structural source of truth where available
- Use Spotify to improve hit rate and confidence for mainstream modern music
- Prefer whichever source gives the strongest exact title and artist agreement

---

## Input Types to Expect

The component should handle:

- `Artist - Title`
- `Title`
- `Artist Title`
- `Artist - Title (Remix)`
- `Artist - Title Radio Edit`
- `Artist - Title SoundtrackName`
- typo-heavy strings
- strings with bad separators
- strings with duplicated metadata
- strings copied from filenames or download titles

Examples:
- `Avicii - Levels`
- `HUNTRIX - What It Sounds Like KPop Demon Hunters`
- `Daft Punk Get Lucky`
- `Calvin Harris - Miracle ft Ellie Goulding`
- `Tayler Swift - Blank Space`

---

## Step 1: Preprocess and Normalise

Before searching, create a normalised working version of the input.

### Actions
- trim whitespace
- collapse repeated spaces
- normalise dash types to a plain hyphen
- strip surrounding quotes
- remove file extensions if present
- remove obvious junk tokens such as:
  - `.mp3`
  - `.flac`
  - `official video`
  - `lyrics`
  - `HD`
  - `audio`
- preserve the original raw input separately

### Example
Input:
`HUNTRIX - What It Sounds Like KPop Demon Hunters`

Normalised working string:
`huntrix - what it sounds like kpop demon hunters`

---

## Step 2: Parse Structure

Attempt to split the string into probable parts.

### Preferred parsing order

1. `artist - title`
2. `artist : title`
3. `artist | title`
4. if no separator, attempt heuristic split
5. also keep the whole string as a fallback search candidate

### Output from parser
Return:
- probable artist
- probable title
- extra context tokens
- parse confidence

### Example parse
Input:
`HUNTRIX - What It Sounds Like KPop Demon Hunters`

Likely parse:
- probable_artist: `HUNTRIX`
- probable_title: `What It Sounds Like KPop Demon Hunters`
- extra_context: empty at first pass
- parse_confidence: medium

---

## Step 3: Detect Contextual Noise

Some suffix text is not part of the title. It may describe:
- film name
- series name
- remix pack
- live version context
- source platform
- featuring credits pasted into title area

Build a light ruleset to detect and isolate this.

### Common context indicators
- `from`
- `feat`
- `ft`
- `featuring`
- `original motion picture soundtrack`
- `soundtrack`
- `from the film`
- `from the netflix film`
- franchise or show names appended after the title

### Heuristic
If the candidate title becomes much stronger after removing trailing context tokens, search both:
- full version
- stripped core version

### Example
`What It Sounds Like KPop Demon Hunters`

Generate:
- core title candidate: `What It Sounds Like`
- contextual suffix candidate: `KPop Demon Hunters`

---

## Step 4: Generate Search Candidates

Do not search only once. Build a small set of candidate queries.

For the example above:

1. artist=`HUNTRIX`, title=`What It Sounds Like KPop Demon Hunters`
2. artist=`HUNTRIX`, title=`What It Sounds Like`
3. whole query=`HUNTRIX What It Sounds Like KPop Demon Hunters`
4. fuzzy artist variant search for `HUNTR/X`
5. title-only fallback: `What It Sounds Like`

### Candidate expansion ideas
- replace `/` with nothing and vice versa
- remove punctuation
- test common typo variants
- test title with and without bracketed qualifiers
- test featuring info as separate credits

---

## Step 5: Query Metadata Providers

For each candidate query:
- search the primary metadata provider
- collect top N results
- optionally search secondary provider if confidence is low or results are sparse

### Store candidate result fields
- source
- source ID
- artist name
- track title
- release title if available
- credited artists
- aliases if available
- score from source if supplied
- raw payload for debugging

---

## Step 6: Score and Rank Matches

Scoring should be explicit and weighted. Do not rely only on the provider's ranking.

### Suggested scoring dimensions

#### Artist score
Compare input artist with candidate artist:
- exact match
- normalised exact match
- alias match
- fuzzy similarity
- stylised punctuation tolerance

Examples:
- `HUNTRIX` vs `HUNTR/X` should score strongly
- `Tayler Swift` vs `Taylor Swift` should score strongly

#### Title score
Compare probable title and stripped title against candidate title:
- exact match
- normalised exact match
- title without brackets
- fuzzy similarity
- prefix match

#### Context score
Reward candidates where extra context aligns with:
- soundtrack title
- film name
- series name
- remix or edit descriptor

#### Penalty score
Penalise:
- wrong artist
- title only vaguely similar
- candidate looks like album not track
- candidate is a cover when original was more likely
- candidate only matches a noisy suffix

### Example weighted model

```text
total_score =
    artist_score * 0.40
  + title_score * 0.45
  + context_score * 0.10
  + popularity_or_source_rank * 0.05
  - penalties
```

---

## Step 7: Confidence Decision

After ranking candidates, decide whether there is a usable answer.

### Suggested thresholds
- **High confidence**
  - strong artist and title agreement
  - clear correction path
- **Medium confidence**
  - title is strong, artist slightly ambiguous
  - multiple plausible versions exist
- **Low confidence**
  - weak similarity only
  - no strong canonical candidate

### Behaviour
- High confidence: return corrected canonical result
- Medium confidence: return best match and mark as tentative
- Low confidence: return unresolved and optionally ask for clarification upstream

---

## Step 8: Build the Correction Result

Return both validation and correction details.

### Recommended response structure

```json
{
  "input": "HUNTRIX - What It Sounds Like KPop Demon Hunters",
  "parsed": {
    "artist": "HUNTRIX",
    "title": "What It Sounds Like KPop Demon Hunters"
  },
  "is_valid_exact": false,
  "best_match": {
    "artist": "HUNTR/X",
    "title": "What It Sounds Like",
    "extended_title": "What It Sounds Like (from the Netflix film KPop Demon Hunters)",
    "source": "MusicBrainz or Spotify",
    "source_id": "example-id"
  },
  "corrections": [
    {
      "field": "artist",
      "from": "HUNTRIX",
      "to": "HUNTR/X"
    },
    {
      "field": "title",
      "from": "What It Sounds Like KPop Demon Hunters",
      "to": "What It Sounds Like"
    }
  ],
  "confidence": "high",
  "alternatives": []
}
```

---

## Matching Rules Worth Implementing

### 1. Separate artist and title scoring
Do not score the whole string only. Artist and title should be evaluated independently.

### 2. Normalise before fuzzy matching
Use lowercase, remove punctuation, collapse spaces, and normalise common separators before computing similarity.

### 3. Preserve stylised official names
Normalisation is for matching only. Output should preserve official styling:
- `HUNTR/X`
- `P!nk`
- `Ke$ha`

### 4. Strip contextual suffixes carefully
Do not always remove trailing words. Search both the raw and stripped forms before deciding.

### 5. Prefer track-level matches over release-level matches
If a provider returns album, release, and track objects, prioritise tracks/recordings.

### 6. Keep multiple plausible variants
For cases like:
- radio edit
- original mix
- remastered
- live
return alternatives if the top result is not far ahead.

---

## Suggested Internal Functions

```text
normalise_input(raw: str) -> NormalisedInput
parse_candidate(normalised: str) -> ParsedCandidate
extract_context(parsed: ParsedCandidate) -> ParsedCandidate
generate_queries(parsed: ParsedCandidate) -> list[SearchQuery]
search_sources(queries: list[SearchQuery]) -> list[ProviderResult]
score_candidate(input_data, provider_result) -> ScoredResult
rank_candidates(scored_results) -> list[ScoredResult]
build_response(raw, parsed, ranked_results) -> ValidationResult
```

---

## Suggested Processing Pseudocode

```python
def validate_track(raw_input: str) -> dict:
    original = raw_input
    normalised = normalise_input(raw_input)

    parsed = parse_candidate(normalised)
    parsed = extract_context(parsed)

    queries = generate_queries(parsed)

    provider_results = search_sources(queries)

    scored = []
    for result in provider_results:
        scored.append(score_candidate(parsed, result))

    ranked = sorted(scored, key=lambda x: x.total_score, reverse=True)

    return build_response(original, parsed, ranked)
```

---

## Example Walkthrough

### Raw input
`HUNTRIX - What It Sounds Like KPop Demon Hunters`

### Preprocess
- lowercase and clean separators
- keep original

### Parse
- artist: `HUNTRIX`
- title: `What It Sounds Like KPop Demon Hunters`

### Context stripping
- detect likely franchise suffix
- generate core title: `What It Sounds Like`

### Query generation
- `HUNTRIX + What It Sounds Like KPop Demon Hunters`
- `HUNTRIX + What It Sounds Like`
- `What It Sounds Like`
- variant artist search around `HUNTR/X`

### Candidate evaluation
Best candidate likely:
- artist: `HUNTR/X`
- title: `What It Sounds Like`

### Final output
- exact input valid: false
- corrected official form returned
- confidence: high

---

## Edge Cases

### Featuring credits
Input:
`Calvin Harris - Miracle ft Ellie Goulding`

Need to support:
- title stays `Miracle`
- featured artist may be part of track credit, not title

### Remixes and edits
Input:
`Fisher - Losing It radio edit`

Should detect:
- base title: `Losing It`
- variant: `Radio Edit`

### Misspelled artist only
Input:
`Tayler Swift - Blank Space`

Should correct artist only

### Misspelled title only
Input:
`Avicii - Leves`

Should correct title only

### No separator
Input:
`Daft Punk Get Lucky`

Need a fallback strategy:
- whole-string search
- title-heavy and artist-heavy candidate generation

### Ambiguous songs
Input:
`Hello`

Should likely remain unresolved unless artist is also provided

---

## Storage and Observability

For debugging and future tuning, log:
- raw input
- normalised input
- parsed artist/title
- generated queries
- top candidate scores
- rejected candidates
- final confidence

This will help improve scoring rules over time.

---

## Recommendation for Inclusion in Existing Project

Build this as a standalone service or module with:
- a provider abstraction layer
- a scoring engine
- a normalisation and parsing layer
- a clean JSON response contract

That keeps the metadata provider swappable and allows scoring logic to evolve without changing the rest of the application.

Suggested module boundaries:
- `providers/`
- `matching/`
- `normalisation/`
- `models/`
- `service/track_validator.py`

---

## Final Notes for the Coding Agent

Key implementation priorities:
1. keep the raw input unchanged for traceability
2. normalise aggressively for matching, but never for final display
3. separate artist, title, and context scoring
4. search both raw and stripped title variants
5. return confidence and alternatives, not just one forced answer
6. design for provider fallback, not provider lock-in
