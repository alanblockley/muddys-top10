# Spotify Playlist Setup

This guide walks you through setting up automated weekly Spotify playlist generation for Muddy's Top 10.

## Overview

Every Saturday at 2am PST, the system will automatically:
1. Generate the current week's Top 10 chart
2. Search for each track on Spotify
3. Create a new public playlist named "Muddy's Top 10 - [Date]"
4. Add all found tracks to the playlist

## Prerequisites

1. **Spotify Developer Account**
   - Go to https://developer.spotify.com/dashboard
   - Create an app (or use existing one)
   - Note your Client ID and Client Secret

2. **Spotify App Configuration**
   - In your Spotify app settings, add your CloudFront URL as a Redirect URI:
     ```
     https://YOUR_CLOUDFRONT_URL/api/spotify/callback
     ```
   - Find your CloudFront URL in the AWS Console or from the SAM deployment outputs
   - Required scopes (automatically requested by the OAuth flow):
     - `playlist-modify-public`
     - `playlist-modify-private`

3. **Decide Which Spotify Account to Use**
   - **Option A**: Use your personal Spotify account (playlists appear on your profile)
   - **Option B**: Create a dedicated "Muddy's Top 10" Spotify account (recommended for cleaner separation)

4. **Deploy with Spotify Credentials**
   - Make sure your SAM stack is deployed with Spotify credentials:
     ```bash
     sam deploy --parameter-overrides \
       SpotifyClientId=your_client_id \
       SpotifyClientSecret=your_client_secret
     ```

## Setup Steps (Admin Panel Method)

### 1. Log into Admin Panel

Go to your CloudFront URL and navigate to the admin panel:

```
https://YOUR_CLOUDFRONT_URL/admin.html
```

Log in with your Cognito credentials.

### 2. Go to Spotify Tab

Click the "🎵 Spotify" tab in the admin panel.

### 3. Connect Spotify Account

1. Click the "Connect Spotify Account" button
2. You'll be redirected to Spotify's authorization page
3. Log in with the Spotify account you want to use for playlists
4. Approve the requested permissions:
   - Create and modify public playlists
   - Create and modify private playlists
5. You'll be redirected back to the admin panel
6. You should see a success message: "Spotify connected successfully!"

**What happens behind the scenes:**
- OAuth flow exchanges authorization code for access and refresh tokens
- Refresh token is securely stored in AWS Secrets Manager
- The token is used to generate playlists without requiring re-authentication

### 4. Verify Connection

The Spotify tab should now show:
- ✓ **Connected** status (green banner)
- "Weekly playlists will be generated automatically every Saturday at 2am PST"

### 5. Test the Playlist Generator (Optional)

You can manually trigger the Lambda to test it:

```bash
aws lambda invoke \
  --function-name muddys-top10-playlist-generator \
  --payload '{}' \
  /tmp/playlist-output.json

cat /tmp/playlist-output.json
```

**Expected output:**
```json
{
  "statusCode": 200,
  "body": "{\"message\": \"Playlist created successfully\", \"playlist_id\": \"...\", \"playlist_url\": \"https://open.spotify.com/playlist/...\", \"tracks_added\": 10}"
}
```

Check the Spotify account - you should see a new playlist!

## Automated Schedule

The playlist generator runs automatically via EventBridge:

- **Schedule**: Every Saturday at 2am PST (10am UTC)
- **Timing**: 2 hours before the chart resets (4am PST)
- **Why 2 hours early**: Gives you time to review/share the playlist before the new chart week starts

**Note about DST**: EventBridge uses UTC, which doesn't account for daylight saving time. During Pacific Daylight Time (summer), the playlist will generate at 3am PDT instead of 2am PST.

## Monitoring

### Check CloudWatch Logs

```bash
aws logs tail /aws/lambda/muddys-top10-playlist-generator --follow
```

### View Recent Playlists

Check the Spotify account's public playlists:
```
https://open.spotify.com/user/YOUR_USER_ID
```

### Disable Automatic Generation

If you need to temporarily disable:

```bash
# Get the rule name
aws events list-rules --name-prefix muddys-top10

# Disable it
aws events disable-rule --name <rule-name>

# Re-enable later
aws events enable-rule --name <rule-name>
```

## Troubleshooting

### "Refresh token not yet configured" Error

You haven't connected Spotify yet. Go to the admin panel → Spotify tab → Connect Spotify Account.

### "Missing Spotify credentials" Error

Make sure your SAM deployment includes the Spotify Client ID and Secret parameters:

```bash
sam deploy --parameter-overrides \
  SpotifyClientId=your_client_id \
  SpotifyClientSecret=your_client_secret
```

### "Failed to get Spotify user" Error

The refresh token may have been revoked or expired. Possible causes:
- User changed their Spotify password
- User manually revoked app access in Spotify settings
- Long period of inactivity

**Solution**: Go to admin panel → Spotify tab → Connect Spotify Account to re-authorize.

### Tracks Not Found on Spotify

Some tracks may not be available on Spotify. The playlist will include only the tracks that were found. Check the CloudWatch logs to see which tracks couldn't be found:

```bash
aws logs tail /aws/lambda/muddys-top10-playlist-generator
```

Look for lines like:
```
Searching for: Artist Name - Track Title
  Not found on Spotify
```

### Rate Limiting

The Spotify provider already includes rate limit handling. If you hit rate limits:
- The Lambda will skip remaining tracks and create a partial playlist
- Check CloudWatch logs for "Rate limited" messages
- The next week's generation should work normally

## How It Works

1. **EventBridge Schedule** triggers the Lambda every Saturday at 2am PST
2. **Lambda reads refresh token** from Secrets Manager
3. **Exchanges refresh token for access token** (expires in 1 hour)
4. **Queries DynamoDB** for the current week's Top 10
5. **Searches Spotify** for each track using artist and title
6. **Creates playlist** in the authorized user's account
7. **Adds tracks** to the playlist (up to 10 tracks)

## Security Notes

- **Refresh token** is stored securely in AWS Secrets Manager (encrypted at rest)
- **Access token** is never persisted (only exists in Lambda memory for ~1 hour max)
- **Client credentials** are stored as CloudFormation parameters with NoEcho=true
- **Playlists** are public by default (can be changed in `src/playlist-generator/app.py`)

## Customization

### Change Playlist Privacy

Edit `src/playlist-generator/app.py`:

```python
playlist_id = spotify_provider.create_playlist(
    user_id=user_id,
    name=playlist_name,
    description=playlist_description,
    public=False  # Change to False for private playlists
)
```

### Change Playlist Name Format

Edit the `playlist_name` variable in `src/playlist-generator/app.py`:

```python
playlist_name = f"Muddy's Top 10 - Week of {now.strftime('%B %d, %Y')}"
```

### Change Schedule

Edit `template.yaml` and modify the cron expression:

```yaml
Schedule: 'cron(0 10 ? * SAT *)'  # Every Saturday at 10am UTC (2am PST)
```

Cron format: `cron(minute hour day-of-month month day-of-week year)`

Examples:
- `cron(0 9 ? * SAT *)` - Saturday 1am PST (9am UTC)
- `cron(0 11 ? * SAT *)` - Saturday 3am PST (11am UTC)
- `cron(0 10 ? * FRI *)` - Friday 2am PST (10am UTC)

## Next Steps

After setup is complete:
1. Wait for the next Saturday 2am PST (or manually invoke to test)
2. Check the Spotify account for the new playlist
3. Share the playlist URL on social media
4. Consider adding a "Latest Playlist" link to your website
