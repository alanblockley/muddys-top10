# Spotify Playlist Setup (Command-Line Method)

**NOTE**: The recommended method is to use the Admin Panel OAuth flow. See [SPOTIFY_PLAYLIST_SETUP.md](SPOTIFY_PLAYLIST_SETUP.md) for instructions.

This document describes the alternative command-line method using `tools/spotify-authorize.py`.

## When to Use This Method

- You prefer command-line tools
- You want to test OAuth flow locally before deploying
- The admin panel OAuth isn't working

## Prerequisites

Same as the admin panel method - see [SPOTIFY_PLAYLIST_SETUP.md](SPOTIFY_PLAYLIST_SETUP.md#prerequisites), but use this redirect URI in your Spotify app:

```
http://127.0.0.1:8888/callback
```

## Setup Steps

### 1. Run the Authorization Script

```bash
# Set your Spotify credentials
export SPOTIFY_CLIENT_ID=your_client_id_here
export SPOTIFY_CLIENT_SECRET=your_client_secret_here

# Run the authorization script
python3 tools/spotify-authorize.py
```

**What happens:**
1. Browser opens to Spotify authorization page
2. Log in with the account you want to use for playlists
3. Approve the requested permissions
4. Script receives the authorization code
5. Script exchanges it for a refresh token
6. Refresh token is displayed in the terminal

### 2. Store the Refresh Token in AWS Secrets Manager

Copy the refresh token from the script output and run:

```bash
# Update the secret with your actual refresh token
aws secretsmanager update-secret \
  --secret-id muddys-top10-spotify-refresh-token \
  --secret-string '{"refresh_token":"YOUR_REFRESH_TOKEN_HERE"}'
```

**Note**: The secret is already created by the SAM template with a placeholder value, so use `update-secret` not `create-secret`.

### 3. Test the Playlist Generator

```bash
aws lambda invoke \
  --function-name muddys-top10-playlist-generator \
  --payload '{}' \
  /tmp/playlist-output.json

cat /tmp/playlist-output.json
```

## Troubleshooting

### "redirect_uri: Not matching configuration" Error

Make sure you added `http://127.0.0.1:8888/callback` (not `localhost`) to your Spotify app's redirect URIs.

### Browser Security Warning

Some browsers may show a warning about the redirect URI not being secure. This is expected for `http://127.0.0.1` and can be safely ignored for local OAuth flows.

### Port Already in Use

If port 8888 is already in use, you can modify the script to use a different port. Edit both the `REDIRECT_URI` variable and the `HTTPServer` port in `tools/spotify-authorize.py`.
