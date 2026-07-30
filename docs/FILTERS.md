# Top 10 Filters

Configuration for filtering tracks from the Top 10 chart (tracks remain in history).

## Quick Setup

Run the configuration script:

```bash
./configure-filters.sh
```

This sets up default filters for:
- Station announcements (all Muddy's/Muddys Music Cafe variations)
- Roadshow announcements (all Muddy's/Muddys Roadshow variations)
- DJ announcements (MUDDY's - DJ ... on MIC)
- Dedication messages with URLs
- Any track containing URLs

## Filter Patterns

Filters use regular expressions (regex). The patterns are:

| Pattern | Matches | Example |
|---------|---------|---------|
| `^Muddy'?s Music Cafe` | Station IDs (with or without apostrophe) | "Muddys Music Cafe - Cuddles Estates 3", "Muddy's Music Cafe - Off The Dial" |
| `^Muddy'?s Roadshow` | Roadshow announcements (with or without apostrophe) | "Muddys Roadshow - Dreamland Designs", "Muddy's Roadshow - Event Name" |
| `^Send your.*http` | Dedication messages with URLs | "Send your [http://...] requests..." |
| `https?://` | Any track with http:// or https:// | Any URL |
| `secondlife:///` | SecondLife URLs | "secondlife:///app/agent/..." |
| `^MUDDY.*DJ.*on MIC` | DJ announcements | "MUDDY's - DJ OLIVER on MIC" |

## Manual Configuration

### View Current Filters

```bash
API_URL=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

curl "$API_URL/config" | jq .top10_filters
```

### Update Filters

```bash
curl -X PUT "$API_URL/config" \
  -H "Content-Type: application/json" \
  -d '{
    "top10_filters": [
      "^Muddy'\''?s Music Cafe",
      "^Muddy'\''?s Roadshow",
      "https?://",
      "secondlife:///"
    ]
  }'
```

### Add a New Filter

Get current filters, add your pattern, then PUT:

```bash
# Get current config
curl "$API_URL/config" > config.json

# Edit config.json to add your pattern to top10_filters array

# Upload
curl -X PUT "$API_URL/config" \
  -H "Content-Type: application/json" \
  -d @config.json
```

### Clear All Filters

```bash
curl -X PUT "$API_URL/config" \
  -H "Content-Type: application/json" \
  -d '{"top10_filters": []}'
```

## Regex Pattern Guide

Common patterns:

| Pattern | Description | Example Matches |
|---------|-------------|-----------------|
| `^text` | Starts with "text" | "text at start" ✅, "not text" ❌ |
| `text$` | Ends with "text" | "ends with text" ✅, "text not end" ❌ |
| `.*` | Any characters | Matches anything |
| `https?://` | http or https URL | "http://example.com", "https://example.com" |
| `\d+` | One or more digits | "123", "3" |
| `[Dd]J` | DJ or dj | "DJ", "dj" |
| `\|` | Pipe character (escaped) | "|" |
| `'?` | Optional apostrophe | "Muddy's" or "Muddys" |

### Examples

**Block all tracks with "Remix" in the name:**
```json
"Remix"
```

**Block tracks starting with "DJ":**
```json
"^DJ "
```

**Block tracks ending with "(Live)":**
```json
"\\(Live\\)$"
```

**Block tracks with phone numbers:**
```json
"\\d{3}-\\d{3}-\\d{4}"
```

**Block multiple artists:**
```json
"(Artist1|Artist2|Artist3)"
```

## How It Works

1. **Filters are stored** in DynamoDB config table under key `top10_filters`
2. **Filter patterns are regex** - tested case-insensitively against track names
3. **Filtered tracks are excluded** from Top 10 calculation only
4. **History is unaffected** - all tracks remain in history view
5. **Week-over-week comparison** uses filtered data for both weeks

### Processing Flow

```
Get all tracks for current week
    ↓
For each track:
    ↓
    Check against all filter patterns
    ↓
    If match found → exclude from Top 10
    ↓
    If no match → include in Top 10
    ↓
Count remaining tracks
    ↓
Rank by play count
    ↓
Return Top 10
```

## Testing Filters

### Test with curl

```bash
# Get Top 10 with filters applied
curl "$API_URL/top10" | jq '.top10[].track'

# Check if specific track would be filtered
# (inspect the results - filtered tracks won't appear)
```

### Test Locally

Create a test script:

```python
import re

def should_filter(track, patterns):
    for pattern in patterns:
        if re.search(pattern, track, re.IGNORECASE):
            return True
    return False

filters = [
    "^Muddys Music Cafe - Cuddles Estates",
    "https?://"
]

test_tracks = [
    "Muddys Music Cafe - Cuddles Estates 3",
    "Artist - Song Title",
    "Send your http://example.com requests"
]

for track in test_tracks:
    filtered = should_filter(track, filters)
    print(f"{'FILTER' if filtered else 'KEEP'}: {track}")
```

## Troubleshooting

### Pattern Not Working

**Issue:** Filter pattern not matching expected tracks

**Solutions:**
1. Test your regex at https://regex101.com/
2. Remember patterns are case-insensitive
3. Escape special characters: `\.` `\(` `\)` `\[` `\]` `\|`
4. Use `.*` for "any characters"

### Too Many Tracks Filtered

**Issue:** Top 10 is empty or has too few tracks

**Check:**
```bash
curl "$API_URL/config" | jq .top10_filters
```

Look for overly broad patterns like:
- `.*` (matches everything)
- `.` (matches everything)
- `a` (matches any track with letter "a")

### Filters Not Applied

**Issue:** Filtered tracks still appearing in Top 10

**Solutions:**
1. Verify filters are saved:
   ```bash
   curl "$API_URL/config" | jq .top10_filters
   ```

2. Check Lambda logs for errors:
   ```bash
   sam logs -n ApiFunction --stack-name muddys-now-playing --tail
   ```

3. Test the pattern:
   ```bash
   # Pattern should appear in filter list
   curl "$API_URL/config" | jq '.top10_filters[]' | grep "your-pattern"
   ```

## Best Practices

1. **Start simple** - Add one pattern at a time
2. **Test first** - Verify pattern matches intended tracks
3. **Be specific** - Narrow patterns avoid false positives
4. **Document** - Comment why each filter exists
5. **Review regularly** - Remove outdated filters

## Examples

### Block Station IDs and Roadshow Only

```json
{
  "top10_filters": [
    "^Muddy'?s Music Cafe",
    "^Muddy'?s Roadshow"
  ]
}
```

### Block URLs and DJ Announcements

```json
{
  "top10_filters": [
    "https?://",
    "secondlife:///",
    "^MUDDY.*DJ.*on MIC"
  ]
}
```

### Block Specific Artists

```json
{
  "top10_filters": [
    "^Artist Name - ",
    "^Another Artist - "
  ]
}
```

### Block Everything Except Music

```json
{
  "top10_filters": [
    "^Muddy'?s Music Cafe",
    "^Muddy'?s Roadshow",
    "^MUDDY",
    "^Send your",
    "https?://",
    "secondlife:///",
    "^DJ ",
    "\\(Live\\)",
    "\\[.*\\]"
  ]
}
```

## Support

For help with regex patterns, see:
- https://regex101.com/ (interactive tester)
- https://regexr.com/ (reference guide)

For API issues, check Lambda logs:
```bash
sam logs -n ApiFunction --stack-name muddys-now-playing --tail
```
