# Shoutcast Stream Formats

The poller supports two Shoutcast metadata formats with automatic detection.

## Supported Formats

### 1. 7.html Format (Legacy Shoutcast v1)

**URL Pattern**: Ends with `7.html`

**Example URL**:
```
http://muddys.digistream.info:20398/7.html
```

**Response Format** (CSV):
```html
<html><body>56,1,62,500,46,128,Artist - Song Title</body></html>
```

**Fields**:
```
field[0] = Current Listeners
field[1] = Stream Status (1=online, 0=offline)
field[2] = Peak Listeners
field[3] = Max Listeners
field[4] = Unique Listeners
field[5] = Bitrate
field[6+] = Current Song (may contain commas)
```

**Parsing**:
- Remove HTML tags
- Split on comma
- Take field[6] onwards (handles song titles with commas)
- HTML unescape

### 2. stats?sid= Format (Shoutcast v2)

**URL Pattern**: Contains `stats?` or `stats&`

**Example URLs**:
```
http://stream.example.com/stats?sid=1
http://stream.example.com/admin.cgi?mode=viewxml&sid=1
```

**Response Format** (XML):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<SHOUTCASTSERVER>
  <CURRENTLISTENERS>82</CURRENTLISTENERS>
  <PEAKLISTENERS>225</PEAKLISTENERS>
  <MAXLISTENERS>500</MAXLISTENERS>
  <UNIQUELISTENERS>79</UNIQUELISTENERS>
  <AVERAGETIME>2275</AVERAGETIME>
  <SERVERGENRE>Unspecified</SERVERGENRE>
  <SERVERURL>http://localhost/</SERVERURL>
  <SERVERTITLE>Muddy's Music Cafe AutoDJ</SERVERTITLE>
  <SONGTITLE>Live @ Muddy's Music Cafe - DJ Twstd</SONGTITLE>
  <STREAMHITS>256159</STREAMHITS>
  <STREAMSTATUS>1</STREAMSTATUS>
  <BITRATE>128</BITRATE>
  <SAMPLERATE>44100</SAMPLERATE>
  <CONTENT>audio/mpeg</CONTENT>
  <VERSION>2.6.1.777 (posix(linux x64))</VERSION>
  <BACKUPSTATUS>0</BACKUPSTATUS>
</SHOUTCASTSERVER>
```

**Parsing**:
- Parse XML
- Extract `<SONGTITLE>` element
- Extract `<BACKUPSTATUS>` element (optional)
- HTML unescape

**Fields Used**:
- `<SONGTITLE>` - Current playing track (required)
- `<BACKUPSTATUS>` - Backup stream indicator (optional)
  - `0` = Normal/primary stream
  - `1` = Backup/failover stream active

When backup status is `1`, a 🔄 icon appears next to the track in the History view (not in Top 10).

## Automatic Format Detection

The poller automatically detects the format in this order:

1. **URL-based detection**:
   - If URL ends with `7.html` → Use CSV parser
   - If URL contains `stats?` → Use XML parser

2. **Content-based detection** (fallback):
   - If response starts with `<?xml` or `<SHOUTCASTSERVER` → Use XML parser
   - Otherwise → Use CSV parser

## Configuration

### Using 7.html Format

```bash
sam deploy --parameter-overrides \
    StreamUrl=http://muddys.digistream.info:20398/7.html
```

Or in `samconfig.toml`:
```toml
parameter_overrides = "StreamUrl=http://muddys.digistream.info:20398/7.html ..."
```

### Using XML Format

```bash
sam deploy --parameter-overrides \
    StreamUrl=http://stream.example.com/stats?sid=1
```

Or in `samconfig.toml`:
```toml
parameter_overrides = "StreamUrl=http://stream.example.com/stats?sid=1 ..."
```

## Testing

Test the format parsers with sample data:

```bash
# Test basic parsing
python3 tests/test-parser.py

# Test backup status parsing (XML only)
python3 tests/test-backup-status.py
```

**Expected Output** (test-parser.py):
```
Testing 7.html format:
  Result: Artist - Song Title

Testing XML format:
  Result: Live @ Muddy's Music Cafe - DJ Twstd

Testing HTML entities:
  Result: Artist & Friends - Song "Title"
```

**Expected Output** (test-backup-status.py):
```
Test: Normal stream (backup=0)
  ✅ PASS
     Track: Artist Name - Track Title
     Backup: False

Test: Backup stream (backup=1)
  ✅ PASS
     Track: HUNTR/X - What It Sounds Like
     Backup: True
```

## Error Handling

**If parsing fails**:
- Logs error message
- Returns `None` (track not logged)
- Next poll attempt in 1 minute
- No data loss (track will be caught on next successful poll)

**Common issues**:
- **Malformed XML**: Check XML declaration and closing tags
- **Unexpected format**: Verify URL is correct
- **Network timeout**: Check stream server is accessible
- **Empty response**: Verify stream is online

## Lambda Logs

Check parser in action:

```bash
sam logs -n StreamPollerFunction --stack-name muddys-now-playing --tail
```

**Expected logs**:
```
Polling stream...
Using 7.html format parser
Saved: Artist - Song Title
```

Or:
```
Polling stream...
Using XML format parser
Saved: Live @ Muddy's Music Cafe - DJ Twstd
```

## Which Format to Use?

**7.html** (recommended if available):
- Simpler format
- Less data overhead
- Faster parsing
- Works with Shoutcast v1 and v2

**stats?sid=** (use if required):
- Shoutcast v2 only
- More metadata available (listeners, bitrate, etc.)
- Standard XML format
- Future-proof

Both formats work equally well for track detection. Choose based on what your stream server provides.

## Switching Formats

To switch between formats:

1. Update the `StreamUrl` parameter
2. Redeploy:
   ```bash
   sam deploy --parameter-overrides StreamUrl=NEW_URL
   ```

No code changes needed - the poller automatically detects and uses the correct parser.

## Future Enhancements

Potential improvements:
- **Multiple streams**: Support multiple stream URLs
- **Metadata extraction**: Use listener count, bitrate from XML
- **Health monitoring**: Alert if stream goes offline
- **Format validation**: Verify response format before parsing
