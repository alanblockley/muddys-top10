# Spotify OAuth Deployment Guide

> Archived note: this document records the original OAuth deployment change.
> Use `../SPOTIFY_PLAYLIST_SETUP.md` and `../DEPLOYMENT.md` for current setup.

## What Changed

Converted Spotify playlist generation from command-line OAuth to admin panel OAuth flow.

### Before
- Run `tools/spotify-authorize.py` locally
- Manually copy refresh token to AWS Secrets Manager
- Command-line only, no UI

### After
- Click "Connect Spotify Account" in admin panel
- OAuth flow handled automatically via CloudFront
- Refresh token stored automatically in Secrets Manager
- Connection status visible in UI

## Changes Made

### 1. API Lambda (`src/api/app.py`)
- Added `/api/spotify/connect` - Initiates OAuth flow with PKCE
- Added `/api/spotify/callback` - Handles OAuth callback and stores refresh token
- Added `/api/spotify/status` - Checks if Spotify is connected
- Added Secrets Manager write permissions

### 2. Admin Panel (`frontend/admin.html`)
- Added "🎵 Spotify" tab
- Connection status UI (Connected/Not Connected)
- "Connect Spotify Account" button
- Automatic redirect handling for OAuth callbacks
- Success/error message display

### 3. Infrastructure (`template.yaml`)
- Added Secrets Manager write permissions to API Lambda
- Added Spotify OAuth endpoints to API Gateway
- Added Spotify environment variables to API Lambda

### 4. Documentation
- Updated `docs/SPOTIFY_PLAYLIST_SETUP.md` with admin panel instructions
- Created `docs/SPOTIFY_PLAYLIST_SETUP_CLI.md` for command-line method (backup)

## Deployment Steps

### 1. Configure Spotify App

1. Go to https://developer.spotify.com/dashboard
2. Select your Spotify app (or create a new one)
3. Click "Edit Settings"
4. Add Redirect URI:
   ```
   https://YOUR_CLOUDFRONT_URL/api/spotify/callback
   ```
   Replace `YOUR_CLOUDFRONT_URL` with your actual CloudFront domain
5. Save

**How to find your CloudFront URL:**
```bash
aws cloudformation describe-stacks \
  --stack-name muddys-top10 \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
  --output text
```

### 2. Deploy SAM Stack

Make sure to include Spotify credentials:

```bash
sam build

sam deploy --parameter-overrides \
  SpotifyClientId=YOUR_SPOTIFY_CLIENT_ID \
  SpotifyClientSecret=YOUR_SPOTIFY_CLIENT_SECRET
```

### 3. Deploy Frontend

```bash
./scripts/update-frontend.sh
```

This updates the admin panel with the new Spotify tab.

### 4. Connect Spotify (First Time)

1. Go to `https://YOUR_CLOUDFRONT_URL/admin.html`
2. Log in with Cognito
3. Click "🎵 Spotify" tab
4. Click "Connect Spotify Account"
5. Authorize with Spotify (use the account you want playlists created on)
6. You'll be redirected back with success message
7. Status should show "✓ Connected"

### 5. Test (Optional)

Manually invoke the playlist generator to test:

```bash
aws lambda invoke \
  --function-name muddys-top10-playlist-generator \
  --payload '{}' \
  /tmp/playlist-output.json

cat /tmp/playlist-output.json
```

Expected output:
```json
{
  "statusCode": 200,
  "body": "{\"message\": \"Playlist created successfully\", \"playlist_id\": \"...\", \"playlist_url\": \"https://open.spotify.com/playlist/...\", \"tracks_added\": 10}"
}
```

Check the Spotify account - you should see a new playlist!

## Important Notes

### PKCE Flow
- Uses Authorization Code Flow with PKCE (more secure than implicit flow)
- Code verifier stored temporarily in Lambda memory (resets on cold start)
- State parameter prevents CSRF attacks
- For production at scale, consider storing PKCE state in DynamoDB with TTL

### Security
- Refresh token encrypted at rest in Secrets Manager
- Access token never persisted (only in Lambda memory)
- OAuth callback requires valid state parameter
- API endpoints use Cognito authorization (except callback)

### Redirect URIs
Two methods supported:
1. **Admin Panel (recommended)**: `https://YOUR_CLOUDFRONT_URL/api/spotify/callback`
2. **Command-line (backup)**: `http://127.0.0.1:8888/callback`

Add both to your Spotify app if you want flexibility.

### Token Lifecycle
- **Access token**: Expires after 1 hour (not stored)
- **Refresh token**: Never expires (stored in Secrets Manager)
- Refresh token revoked if:
  - User changes Spotify password
  - User revokes app access manually
  - Spotify detects suspicious activity

### Reconnection
If the connection breaks (password change, manual revoke):
1. User will see "Not Connected" status in admin panel
2. Click "Connect Spotify Account" again
3. New refresh token stored automatically

## Monitoring

### Check Connection Status
```bash
aws secretsmanager get-secret-value \
  --secret-id muddys-top10-spotify-refresh-token \
  --query 'SecretString' \
  --output text | jq .
```

Should show:
```json
{
  "refresh_token": "AQD..."
}
```

If it shows `PLACEHOLDER_UPDATE_AFTER_AUTHORIZATION`, Spotify hasn't been connected yet.

### Check CloudWatch Logs

**API Lambda (OAuth flow):**
```bash
aws logs tail /aws/lambda/muddys-top10-api --follow
```

**Playlist Generator Lambda:**
```bash
aws logs tail /aws/lambda/muddys-top10-playlist-generator --follow
```

### Weekly Playlist Generation

Runs automatically every Saturday at 2am PST (10am UTC) via EventBridge.

Check recent playlists:
```
https://open.spotify.com/user/YOUR_SPOTIFY_USER_ID
```

## Troubleshooting

### "redirect_uri: Not matching configuration"
- Make sure you added the correct CloudFront URL to Spotify app settings
- Check for typos (common mistake: trailing slash)
- Must be exact match: `https://YOUR_CLOUDFRONT_URL/api/spotify/callback`

### "Spotify not connected" after clicking Connect
- Check CloudWatch logs for API Lambda
- Verify Spotify credentials are in SAM parameters
- Check API Gateway CORS settings

### OAuth callback shows 404
- Make sure SAM stack is deployed with latest template.yaml
- Verify `/api/spotify/callback` endpoint exists in API Gateway
- Check CloudFront cache (may need to invalidate)

### "Invalid state parameter"
- Lambda cold start cleared PKCE state from memory
- Click "Connect Spotify Account" again to restart flow
- For production: implement DynamoDB state storage with TTL

## Rollback

If OAuth flow isn't working and you need the old command-line method:

```bash
# Use the CLI script
python3 tools/spotify-authorize.py

# Manually update secret
aws secretsmanager update-secret \
  --secret-id muddys-top10-spotify-refresh-token \
  --secret-string '{"refresh_token":"YOUR_REFRESH_TOKEN"}'
```

See [SPOTIFY_PLAYLIST_SETUP_CLI.md](../SPOTIFY_PLAYLIST_SETUP_CLI.md) for details.
