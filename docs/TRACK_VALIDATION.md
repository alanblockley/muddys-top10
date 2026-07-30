# Track Validation System

The track validation system automatically validates and canonicalizes track names using MusicBrainz and Spotify APIs.

## How It Works

### Flow

```
1. Stream poller fetches raw track from Shoutcast
2. Poller cleans track using CLEAN_TITLES.MD rules
3. Poller saves cleaned track to DynamoDB
4. DynamoDB stream triggers TrackValidatorFunction
5. Validator checks if track matches filter patterns:
   - If matches filter → Mark as "promotional", skip validation
   - If doesn't match filter → Validate against music databases
6. Validator updates track record with canonical name + metadata
7. API uses canonical names for display in history and Top 10
```

### Architecture

**TrackValidatorFunction**:
- Triggered by DynamoDB stream on TracksTable
- Processes INSERT events only
- Runs asynchronously (doesn't slow down poller)
- Timeout: 60 seconds
- Memory: 512 MB

**Music Providers**:
- **MusicBrainz** (primary, always used)
  - No API key required
  - Canonical source of truth
  - Good for artist/title normalization
- **Spotify** (secondary, optional)
  - Requires Client ID + Client Secret
  - Better for modern/popular tracks
  - Provides popularity scoring

## DynamoDB Schema

Tracks are stored with additional validation fields:

```python
{
    'pk': 'TRACK',
    'sk': 'TS#1234567890',
    'timestamp': 1234567890,
    'track': 'HUNTRIX - What It Sounds Like KPop Demon Hunters',  # Raw/cleaned
    'canonical_track': 'HUNTR/X - What It Sounds Like',  # Validated canonical
    'artist': 'HUNTR/X',  # Parsed artist
    'title': 'What It Sounds Like',  # Parsed title
    'validation_status': 'validated',  # validated | unvalidated | promotional
    'validation_confidence': 'high',  # high | medium | low
    'music_db_id': 'abc123',  # MusicBrainz or Spotify ID
    'music_db_source': 'musicbrainz',  # musicbrainz | spotify
    'artist_score': 0.95,  # Matching score for artist
    'title_score': 0.92,  # Matching score for title
    'total_score': 0.88,  # Overall matching score
    'ttl': 1234567890  # 90 days
}
```

## Validation Logic

### Step 1: Preprocessing
- Normalize whitespace
- Remove file extensions (.mp3, .flac, etc.)
- Remove junk tokens (HD, official video, lyrics, etc.)

### Step 2: Parsing
- Split on separators: ` - `, ` : `, ` | `
- Extract artist and title
- Detect and separate contextual noise (feat., from the film, etc.)

### Step 3: Search Candidate Generation
Generate multiple search queries:
1. Full artist + title
2. Artist + title with context
3. Artist variants (handle special characters like `/`)
4. Title-only fallback
5. Whole string fallback

### Step 4: Provider Search
- Query MusicBrainz with each candidate
- Query Spotify with each candidate (if credentials available)
- Collect top 10 results from each provider

### Step 5: Scoring
Score each match on multiple dimensions:

**Artist Score (40% weight)**:
- Exact match: 1.0
- Normalized match: 0.95
- Stylized variant (HUNTRIX → HUNTR/X): 0.90
- Fuzzy similarity > 0.85: 0.85
- Lower similarity: penalized

**Title Score (50% weight)**:
- Exact match: 1.0
- Normalized match: 0.95
- Match without context: 0.92
- Match without qualifiers (remix, edit): 0.88
- Fuzzy similarity > 0.85: 0.85
- Lower similarity: penalized

**Popularity Bonus (10% weight)**:
- Spotify popularity: 0-10% boost
- MusicBrainz result position: small boost

### Step 6: Confidence Decision

**High Confidence**:
- Artist score > 0.85 AND title score > 0.85
- Total score > 0.6
- Clear correction path

**Medium Confidence**:
- Artist score > 0.7 AND title score > 0.7
- Total score > 0.6
- Plausible match with some ambiguity

**Low Confidence**:
- Scores below thresholds
- Weak similarity only
- No strong canonical candidate

**Decision**:
- High/Medium confidence: Accept match, use canonical name
- Low confidence: Reject match, keep original name

## Promotional Content Handling

Tracks matching Top 10 filter patterns skip validation entirely:

```python
# These patterns trigger promotional status:
- "^Muddy'?s Music Cafe"
- "^Muddy'?s Roadshow"
- "^MUDDY.*DJ.*on MIC"
- "^Send your.*http"
- "https?://"
- "secondlife:///"
```

**Why?**
- No need to validate station IDs, DJ announcements, URLs
- Saves API calls
- Faster processing
- These are never included in Top 10 anyway

## Examples

### Example 1: Typo Correction

**Input**: `HUNTRIX - What It Sounds Like KPop Demon Hunters`

**Processing**:
1. Parse: artist=`HUNTRIX`, title=`What It Sounds Like KPop Demon Hunters`
2. Detect context: `KPop Demon Hunters` is likely context
3. Generate candidates:
   - `HUNTRIX` + `What It Sounds Like`
   - `HUNTR/X` (variant) + `What It Sounds Like`
4. Search MusicBrainz/Spotify
5. Best match: `HUNTR/X - What It Sounds Like`
6. Scores: artist=0.90, title=0.95, total=0.88
7. Confidence: high

**Output**:
```json
{
    "canonical_track": "HUNTR/X - What It Sounds Like",
    "artist": "HUNTR/X",
    "title": "What It Sounds Like",
    "validation_status": "validated",
    "validation_confidence": "high",
    "music_db_source": "musicbrainz"
}
```

### Example 2: Artist Typo

**Input**: `Tayler Swift - Blank Space`

**Processing**:
1. Parse: artist=`Tayler Swift`, title=`Blank Space`
2. Search with typo
3. Best match: `Taylor Swift - Blank Space`
4. Scores: artist=0.92 (high similarity), title=1.0
5. Confidence: high

**Output**:
```json
{
    "canonical_track": "Taylor Swift - Blank Space",
    "artist": "Taylor Swift",
    "title": "Blank Space",
    "validation_status": "validated",
    "validation_confidence": "high"
}
```

### Example 3: Promotional Content

**Input**: `Muddys Music Cafe - Cuddles Estates 3`

**Processing**:
1. Check filters: matches `^Muddy'?s Music Cafe`
2. Skip validation entirely
3. Mark as promotional

**Output**:
```json
{
    "canonical_track": "Muddys Music Cafe - Cuddles Estates 3",
    "validation_status": "promotional"
}
```

### Example 4: No Match Found

**Input**: `Unknown Artist - Obscure Track Name 12345`

**Processing**:
1. Parse and search
2. No good matches found
3. Best match has confidence=low, score=0.3
4. Reject match

**Output**:
```json
{
    "canonical_track": "Unknown Artist - Obscure Track Name 12345",
    "validation_status": "unvalidated",
    "validation_confidence": "low"
}
```

## Spotify API Setup (Optional)

Spotify provides better coverage for modern/popular tracks but requires API credentials.

### Get Spotify Credentials

1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account
3. Click "Create an App"
4. Fill in app details:
   - App name: "Muddy's Top 10 Tracker"
   - App description: "Track validation for radio station"
5. Click "Create"
6. Copy your Client ID and Client Secret

### Add to SAM Parameters

Update `samconfig.toml`:

```toml
parameter_overrides = "StreamUrl=http://muddys.digistream.info:20398/7.html SpotifyClientId=\"YOUR_CLIENT_ID\" SpotifyClientSecret=\"YOUR_CLIENT_SECRET\""
```

Or set during deployment:

```bash
sam deploy --parameter-overrides \
    StreamUrl=http://muddys.digistream.info:20398/7.html \
    SpotifyClientId=YOUR_CLIENT_ID \
    SpotifyClientSecret=YOUR_CLIENT_SECRET
```

### Without Spotify

If Spotify credentials are not provided, the system works perfectly fine using only MusicBrainz:
- MusicBrainz has extensive coverage
- No API key required
- Good for canonical names
- Slightly less coverage for very new tracks

## API Display

### History Endpoint

Tracks are displayed with canonical names:

```json
{
    "blocks": [
        {
            "block_timestamp": 1234567890,
            "block_label": "2024-01-15 02:00 PM PST",
            "tracks": [
                {
                    "timestamp": 1234567890,
                    "formatted_time": "2024-01-15T14:30:00-08:00",
                    "track": "HUNTR/X - What It Sounds Like",
                    "raw_track": "HUNTRIX - What It Sounds Like KPop Demon Hunters",
                    "validation_status": "validated",
                    "artist": "HUNTR/X",
                    "title": "What It Sounds Like"
                }
            ]
        }
    ]
}
```

### Top 10 Endpoint

Rankings use canonical names to prevent duplicates:

```json
{
    "top10": [
        {
            "rank": 1,
            "track": "HUNTR/X - What It Sounds Like",
            "play_count": 15,
            "previous_rank": null,
            "movement": "new"
        }
    ]
}
```

**Benefit**: Even if the stream metadata has typos or variations, all plays count toward the same canonical track.

## Monitoring

### CloudWatch Logs

View validation logs:

```bash
sam logs -n TrackValidatorFunction --stack-name muddys-now-playing --tail
```

### Check Validation Status

Query tracks to see validation status:

```bash
aws dynamodb query \
    --table-name muddys-now-playing-tracks \
    --index-name timestamp-index \
    --key-condition-expression "pk = :pk" \
    --expression-attribute-values '{":pk":{"S":"TRACK"}}' \
    --projection-expression "track,canonical_track,validation_status,validation_confidence" \
    --limit 20
```

### Metrics to Track

Monitor these in CloudWatch:
- **Validation rate**: % of tracks successfully validated
- **Confidence distribution**: high/medium/low/unvalidated/promotional
- **Lambda errors**: Failures in TrackValidatorFunction
- **API latency**: Impact of validation on API performance (should be none - async)

## Troubleshooting

### Tracks Not Being Validated

**Symptom**: `validation_status` field is missing or always "unvalidated"

**Check**:
1. Verify DynamoDB stream is enabled on TracksTable
2. Check TrackValidatorFunction logs for errors
3. Verify Lambda has permissions to update DynamoDB
4. Check if tracks are being filtered as promotional

```bash
# Check stream status
aws dynamodb describe-table \
    --table-name muddys-now-playing-tracks \
    --query 'Table.StreamSpecification'

# Check Lambda logs
sam logs -n TrackValidatorFunction --stack-name muddys-now-playing --tail
```

### Low Validation Success Rate

**Symptom**: Most tracks show as "unvalidated" with low confidence

**Possible causes**:
1. Track names are heavily corrupted or unusual
2. MusicBrainz API is down
3. Tracks are very obscure/local
4. Network connectivity issues

**Solutions**:
- Add Spotify credentials for better coverage
- Review and improve CLEAN_TITLES.MD rules
- Check MusicBrainz service status
- Manually review low-confidence matches

### Spotify API Errors

**Symptom**: Logs show Spotify authentication failures

**Check**:
1. Verify Client ID and Client Secret are correct
2. Ensure credentials are properly set in Lambda environment
3. Check Spotify API quotas/limits

```bash
# Verify environment variables
aws lambda get-function-configuration \
    --function-name muddys-now-playing-track-validator \
    --query 'Environment.Variables'
```

### Wrong Canonical Names

**Symptom**: Tracks validated to incorrect canonical names

**Causes**:
- Scoring thresholds too low
- Ambiguous track names
- Artist variants not handled well

**Solutions**:
1. Increase confidence thresholds in validator
2. Add more artist variants to normalization
3. Manually review high-score but incorrect matches
4. Improve context extraction rules

## Performance Considerations

### API Rate Limiting

**MusicBrainz**:
- Rate limit: 1 request per second
- User-Agent required (set automatically)
- No API key required

**Spotify**:
- Rate limit: Varies by endpoint (typically generous)
- Requires access token (automatically managed)
- Token cached for 1 hour

### Optimization

Current implementation:
- Batches 10 stream events together
- Waits up to 5 seconds before processing batch
- Processes up to 3 search candidates per track
- Skips promotional content entirely

**Expected load**:
- ~1 track per minute from poller
- ~60 tracks per hour
- ~1440 tracks per day
- Well within API limits

### Cost

**Lambda**:
- Validator runs ~60 times/hour
- 60 seconds timeout, 512 MB memory
- Average execution: ~5 seconds
- Cost: ~$0.50/month

**DynamoDB**:
- Stream reads: included in on-demand pricing
- Extra writes for validation fields: minimal
- Cost: < $0.10/month extra

**APIs**:
- MusicBrainz: Free
- Spotify: Free (within generous limits)

**Total**: ~$0.60/month extra for validation

## Future Enhancements

Potential improvements:
1. **Caching**: Cache validation results to avoid re-validating same tracks
2. **Manual override**: Admin UI to manually set canonical names
3. **Confidence tuning**: Machine learning to improve scoring
4. **Additional providers**: Add Last.fm, Discogs for better coverage
5. **Batch validation**: Backfill historical tracks
6. **Analytics**: Track validation success rates over time
7. **A/B testing**: Compare MusicBrainz vs Spotify accuracy
