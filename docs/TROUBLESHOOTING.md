# Troubleshooting Guide

## Hanging/Ghosted Lambda Executions

### Problem
Track validator Lambda hangs or times out, causing repeated errors in CloudWatch logs.

### Symptoms
- CloudWatch logs show repeated validation attempts for the same track
- Lambda execution duration hits timeout (30 seconds)
- DynamoDB stream backlog building up
- Track shows as "unvalidated" in history

### Causes
1. **API timeouts** - MusicBrainz or Spotify API not responding
2. **Rate limiting** - Too many requests to music APIs
3. **Network issues** - AWS Lambda can't reach external APIs
4. **Malformed track names** - Unusual characters causing API errors

### How to Stop Hanging Executions

#### Option 1: Wait for DynamoDB Stream to Process
DynamoDB Streams automatically retry failed records. After the Lambda times out, the stream will:
- Retry the batch up to the configured retry limit
- Eventually move failed records to a dead letter queue (if configured)
- Stop retrying after max attempts

**Wait time**: Usually 5-10 minutes for retries to exhaust

#### Option 2: Manually Stop the Lambda (Not Recommended)
You **cannot** stop a running Lambda execution directly. AWS will automatically stop it when it hits the timeout.

#### Option 3: Disable the Stream Trigger Temporarily
```bash
# Get the UUID of the event source mapping
aws lambda list-event-source-mappings \
  --function-name muddys-now-playing-track-validator \
  --query 'EventSourceMappings[0].UUID' \
  --output text

# Disable the trigger
aws lambda update-event-source-mapping \
  --uuid <UUID_FROM_ABOVE> \
  --enabled false

# Wait a few minutes for current executions to finish

# Re-enable when ready
aws lambda update-event-source-mapping \
  --uuid <UUID_FROM_ABOVE> \
  --enabled true
```

#### Option 4: Delete Problematic Track from DynamoDB
If a specific track is causing the issue:

```bash
# Find the track in DynamoDB (use admin panel History view)
# Note the timestamp of the problematic track

# Delete it
aws dynamodb delete-item \
  --table-name muddys-now-playing-tracks \
  --key '{"pk":{"S":"TRACK"},"sk":{"S":"TS#<timestamp>"}}'
```

Replace `<timestamp>` with the actual timestamp (e.g., `TS#1711555200`)

### Prevention

#### 1. API Timeouts (Already Implemented)
- MusicBrainz: 10 second timeout
- Spotify: 10 second timeout
- Lambda: 30 second total timeout

#### 2. Error Handling (Already Implemented)
Each provider wrapped in try/except:
```python
try:
    mb_results = mb_provider.search(artist, title)
except Exception as e:
    print(f"MusicBrainz search failed: {e}")
    # Continue to next provider
```

#### 3. Validation Fallback (Already Implemented)
If validation fails, track is marked with:
- `validation_status: 'error'`
- `canonical_track: <original_track_name>`
- `confidence: 'error'`

#### 4. Rate Limit Handling
Current implementation logs rate limit errors but doesn't retry. This is intentional to avoid cascading failures.

### Monitoring

#### Check CloudWatch Logs
```bash
# View validator logs
sam logs -n TrackValidatorFunction --stack-name muddys-now-playing --tail

# Look for patterns like:
# - "Validation failed for"
# - "search failed"
# - "Timeout"
# - "Task timed out"
```

#### Check DynamoDB Stream Status
```bash
# Check for stream lag
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name IteratorAge \
  --dimensions Name=FunctionName,Value=muddys-now-playing-track-validator \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum
```

If `IteratorAge` is high (>30000 ms), the stream is backed up.

### Common Error Messages

#### "Spotify error: HTTP 429"
**Meaning**: Rate limited by Spotify
**Solution**: Wait 1 minute, will auto-retry
**Prevention**: Already implemented - continues with MusicBrainz only

#### "MusicBrainz error: HTTP 503"
**Meaning**: Service temporarily unavailable
**Solution**: Wait and retry
**Prevention**: Already implemented - continues to Spotify

#### "Task timed out after 30.00 seconds"
**Meaning**: Lambda execution exceeded timeout
**Solution**: Track will be marked as 'error' and won't block future tracks
**Prevention**: Timeout is set appropriately

#### "decimal.Decimal object cannot be interpreted as an integer"
**Meaning**: DynamoDB returned Decimal type
**Solution**: Already fixed - uses int() conversion
**Prevention**: Update deployed with fix

### Recovery Steps

If the validator is completely stuck:

1. **Check CloudWatch Logs**
   ```bash
   sam logs -n TrackValidatorFunction --stack-name muddys-now-playing --tail
   ```

2. **Identify Problem Track**
   Look for repeated validation attempts on the same track

3. **Manually Mark Track as Validated**
   ```bash
   aws dynamodb update-item \
     --table-name muddys-now-playing-tracks \
     --key '{"pk":{"S":"TRACK"},"sk":{"S":"TS#<timestamp>"}}' \
     --update-expression "SET validation_status = :status, validation_confidence = :confidence" \
     --expression-attribute-values '{":status":{"S":"error"},":confidence":{"S":"manual_skip"}}'
   ```

4. **Wait for Stream to Process**
   Give it 5-10 minutes to clear the backlog

5. **Verify History**
   Check the admin panel History view to confirm tracks are appearing

### Best Practices

1. **Monitor Regularly**
   - Check CloudWatch logs weekly
   - Watch for repeated errors on same track

2. **Track Problem Patterns**
   - Keep list of tracks that fail validation
   - Check if certain artists/formats cause issues

3. **Update Filter Patterns**
   - Add problematic track patterns to filters
   - Prevents validation attempts on non-music content

4. **API Key Rotation**
   - Spotify credentials can be rotated if hitting rate limits frequently
   - Get new credentials at: https://developer.spotify.com/dashboard

### When to Escalate

Contact AWS Support if:
- Lambda consistently times out even with valid tracks
- DynamoDB stream lag exceeds 1 hour
- Costs spike due to repeated executions
- API timeouts persist for >24 hours

### Related Documentation
- [TRACK_VALIDATION.md](TRACK_VALIDATION.md) - How validation works
- [STREAM_FORMATS.md](STREAM_FORMATS.md) - Stream metadata parsing
- [FILTERS.md](FILTERS.md) - Track filtering configuration
