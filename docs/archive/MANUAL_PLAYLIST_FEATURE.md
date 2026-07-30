# Manual Playlist Generation & Configurable Schedule

> Archived note: this document records implementation history. Use
> `../README.md` and the current Spotify/deployment docs for live operations.

## New Features

### 1. Manual Playlist Generation
Generate a Spotify playlist with the current Top 10 immediately, regardless of schedule.

**Use cases:**
- Test playlist generation before going live
- Create bonus playlists mid-week
- Share current chart on social media right now
- Generate playlist for special events

**How to use:**
1. Go to Admin Panel → Spotify tab
2. Click "📝 Generate Playlist Now"
3. Playlist created with current Top 10 tracks
4. Link displayed to open in Spotify

### 2. Configurable Schedule
Change when automatic playlists are generated (day and time).

**Use cases:**
- Match playlist generation to your promotion schedule
- Generate before/after chart reset (your choice)
- Coordinate with social media posting time

**How to configure:**
1. Go to Admin Panel → Spotify tab → "Automatic Generation Schedule"
2. Select Day (Monday - Sunday)
3. Select Time (12:00am - 11:00pm PST)
4. Click "Save Schedule"
5. EventBridge rule updates automatically

**Default:** Saturday at 2:00am PST (2 hours before chart reset at 4am)

## Changes Made

### API Endpoints

**New endpoint: POST /api/spotify/generate-playlist**
- Requires authentication (Cognito)
- Invokes playlist generator Lambda immediately
- Returns playlist URL and track count
- Used by "Generate Playlist Now" button

**Updated endpoint: GET /api/config**
- Now returns `playlist_generation` config:
  ```json
  {
    "playlist_generation": {
      "day": "saturday",
      "hour": 2
    }
  }
  ```

**Updated endpoint: PUT /api/config**
- Now accepts `playlist_generation` config
- Updates DynamoDB config table
- Triggers schedule updater via DynamoDB stream

### New Lambda: Schedule Updater

**File:** `src/schedule-updater/app.py`

**Purpose:** Updates EventBridge rule when playlist schedule changes

**Trigger:** DynamoDB stream on ConfigTable

**How it works:**
1. Watches for changes to `playlist_generation` config
2. Reads new day/hour from config
3. Converts PST hour to UTC (adds 8 hours)
4. Builds cron expression: `cron(0 {UTC_hour} ? * {DAY} *)`
5. Updates EventBridge rule with new schedule

**Example:**
- User sets: Friday 6:00pm PST
- Lambda converts: Friday 2:00am UTC (next day)
- EventBridge cron: `cron(0 2 ? * SAT *)`

### Admin Panel UI

**New section: Manual Generation**
- "Generate Playlist Now" button
- Status display (success/error)
- Playlist link when successful

**New section: Automatic Generation Schedule**
- Day dropdown (Monday - Sunday)
- Time dropdown (12:00am - 11:00pm PST)
- "Save Schedule" button
- Shows current schedule in connection status banner

**Connection status banner updated:**
- Now shows configured schedule dynamically
- Example: "Weekly playlists will be generated automatically every Friday at 6:00pm PST"

### Infrastructure

**ConfigTable:**
- Added DynamoDB stream (NEW_IMAGE)
- Enables real-time schedule updates

**API Lambda:**
- Added Lambda invoke permission for playlist generator
- Can trigger manual playlist generation

**Schedule Updater Lambda:**
- Permissions to update EventBridge rule
- Triggered by ConfigTable stream
- Timeout: 30 seconds

**EventBridge Rule:**
- Now dynamically updated by schedule updater
- Initial schedule: Saturday 2am PST (cron: 0 10 ? * SAT *)
- Description updated when schedule changes

## Deployment

```bash
sam build
sam deploy
./scripts/update-frontend.sh
```

## Testing

### Test Manual Generation

1. **Admin panel:**
   - Go to Spotify tab
   - Click "Generate Playlist Now"
   - Check Spotify account for new playlist

2. **Command line:**
   ```bash
   curl -X POST \
     -H "Authorization: YOUR_ID_TOKEN" \
     https://YOUR_API/api/spotify/generate-playlist
   ```

### Test Schedule Configuration

1. **Change schedule:**
   - Admin panel → Spotify tab
   - Set: Monday at 10:00am PST
   - Save

2. **Verify EventBridge rule:**
   ```bash
   aws events describe-rule \
     --name muddys-top10-playlist-generatorWeeklySchedule
   ```
   
   Should show: `"ScheduleExpression": "cron(0 18 ? * MON *)"`
   (10am PST = 6pm UTC)

3. **Check CloudWatch logs:**
   ```bash
   aws logs tail /aws/lambda/muddys-top10-schedule-updater --follow
   ```

## Limitations

### DST (Daylight Saving Time)
- EventBridge uses UTC (no DST)
- PST conversion is simple: PST + 8 = UTC
- **During PDT (summer):**
  - User sets: 2am "PST"
  - Actual time: 3am PDT (because we add 8 hours)
  - To get true 2am PDT, user should set to 1am

**Options to fix DST:**
1. Keep current behavior (simple, always PST)
2. Add timezone library and detect DST (complex)
3. Add note in UI: "Times in PST (not PDT)"

**Recommendation:** Keep current behavior, add UI note

### Schedule Update Delay
- Schedule updates are near-instant (DynamoDB stream + Lambda)
- Typical delay: < 5 seconds
- If change doesn't apply immediately, check CloudWatch logs

### Cron Limitations
- EventBridge uses UTC cron expressions
- Minimum granularity: 1 minute
- Can't schedule multiple times per day (current UI)

## Configuration Schema

### playlist_generation config

```json
{
  "day": "monday" | "tuesday" | "wednesday" | "thursday" | "friday" | "saturday" | "sunday",
  "hour": 0-23
}
```

**Example DynamoDB item:**
```json
{
  "configKey": "playlist_generation",
  "value": {
    "day": "friday",
    "hour": 18
  }
}
```

## UI Flow

### First Time (Not Connected)
1. Admin panel shows: "⚠️ Not Connected"
2. Only "Connect Spotify Account" button visible
3. Manual generation and schedule config hidden

### After Connecting
1. Status shows: "✓ Connected - Weekly playlists every Saturday at 2:00am PST"
2. Manual generation section appears
3. Schedule configuration section appears
4. Current schedule loaded into form

### Generating Manually
1. User clicks "Generate Playlist Now"
2. Button shows: "⏳ Generating..."
3. Loading message: "Creating playlist with current Top 10..."
4. Success: Shows playlist link + track count
5. Error: Shows error message

### Changing Schedule
1. User selects day/time
2. Clicks "Save Schedule"
3. Loading spinner appears
4. Success message: "Playlist schedule updated successfully!"
5. Status banner updates with new schedule

## Error Handling

### Manual Generation Errors

**Spotify not connected:**
```json
{
  "error": "Refresh token not yet configured"
}
```
Solution: Connect Spotify first

**No tracks in Top 10:**
```json
{
  "message": "No tracks to add to playlist"
}
```
Solution: Wait until tracks are played

**Spotify API error:**
```json
{
  "error": "Failed to create playlist"
}
```
Solution: Check CloudWatch logs, verify Spotify connection

### Schedule Update Errors

**EventBridge permission denied:**
- Check ScheduleUpdaterFunction IAM permissions
- Verify rule name matches: `${AWS::StackName}-playlist-generatorWeeklySchedule`

**Invalid day/hour:**
- Frontend validation prevents this
- Backend defaults to Saturday 2am if invalid

## Monitoring

### Manual Generation
```bash
# API Lambda (receives request, invokes generator)
aws logs tail /aws/lambda/muddys-top10-api --follow

# Playlist Generator Lambda (creates playlist)
aws logs tail /aws/lambda/muddys-top10-playlist-generator --follow
```

### Schedule Updates
```bash
# Schedule Updater Lambda (watches config changes)
aws logs tail /aws/lambda/muddys-top10-schedule-updater --follow

# Verify rule schedule
aws events describe-rule --name muddys-top10-playlist-generatorWeeklySchedule
```

### Automatic Generation
```bash
# Check recent invocations
aws lambda get-function --function-name muddys-top10-playlist-generator

# View logs
aws logs tail /aws/lambda/muddys-top10-playlist-generator --since 1d
```

## Next Steps

1. **Add DST awareness** (optional)
   - Use `zoneinfo` in schedule-updater
   - Detect if PST or PDT
   - Adjust UTC conversion accordingly

2. **Add multiple schedules** (optional)
   - Support array of schedules: `[{day: 'monday', hour: 10}, {day: 'friday', hour: 18}]`
   - Create multiple EventBridge rules

3. **Add disconnect endpoint** (optional)
   - `/api/spotify/disconnect` endpoint
   - Clears refresh token from Secrets Manager
   - Shows "Disconnect" button functionality

4. **Add playlist history** (optional)
   - Store generated playlists in DynamoDB
   - Show last 10 playlists in admin panel
   - Track which tracks were included

5. **Add notification** (optional)
   - Email/Slack notification when playlist created
   - Include playlist URL and track count
   - Alert on generation failures
