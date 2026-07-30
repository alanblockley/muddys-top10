# Spotify Web API Calls Reference

Complete documentation of all Spotify Web API endpoints used in Muddy's Top 10.

---

## 1. Token Management

### Get Access Token
**Method:** `POST`  
**Endpoint:** `https://accounts.spotify.com/api/token`  
**Purpose:** Exchange refresh token for access token, or get client credentials token

**Headers:**
```
Authorization: Basic {base64(client_id:client_secret)}
Content-Type: application/x-www-form-urlencoded
```

**Body (Refresh Token Flow):**
```
grant_type=refresh_token&refresh_token={refresh_token}
```

**Body (Client Credentials Flow):**
```
grant_type=client_credentials
```

**Response:** `200 OK`
```json
{
  "access_token": "BQD...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "playlist-modify-public playlist-modify-private ugc-image-upload"
}
```

**Used By:** All Spotify API calls  
**Location:** `music_providers.py:get_access_token()`  
**Notes:** 
- Refresh token flow used for playlist modification (user context)
- Client credentials flow used for search only (no user context)
- Access tokens expire after 1 hour
- Refresh tokens never expire (unless revoked)

---

## 2. Search for Tracks

### Search Tracks
**Method:** `GET`  
**Endpoint:** `https://api.spotify.com/v1/search`  
**Purpose:** Find tracks by artist and title to get Spotify URIs

**Query Parameters:**
```
q=artist:"{artist}" track:"{title}"
type=track
limit=10
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:** `200 OK`
```json
{
  "tracks": {
    "items": [
      {
        "id": "4iV5W9uYEdYUVa79Axb7Rh",
        "name": "Track Title",
        "artists": [{"name": "Artist Name"}],
        "album": {"name": "Album Name"},
        "uri": "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
      }
    ]
  }
}
```

**Used By:** Track URI lookup  
**Location:** `music_providers.py:search()`, `get_track_uri()`  
**Scopes Required:** None (can use client credentials)  
**Notes:** Returns up to 10 matches, sorted by relevance

---

## 3. User Profile

### Get Current User
**Method:** `GET`  
**Endpoint:** `https://api.spotify.com/v1/me`  
**Purpose:** Get authenticated user's profile (ID, display name)

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:** `200 OK`
```json
{
  "id": "317vyyng6qvtj4ibanvybny4zkvq",
  "display_name": "DJ Toohey",
  "email": "user@example.com",
  "product": "premium"
}
```

**Used By:** Playlist creation, token validation  
**Location:** `music_providers.py:get_current_user()`, `check_token_scopes()`  
**Scopes Required:** `user-read-private` or `user-read-email`  
**Notes:** Also used to validate token and check authentication

---

## 4. Playlist Management

### Get User's Playlists
**Method:** `GET`  
**Endpoint:** `https://api.spotify.com/v1/me/playlists`  
**Purpose:** List user's playlists to find existing "Muddy's Top 10"

**Query Parameters:**
```
limit=50
offset=0
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "7Dzb7magODhR205xKnbSoC",
      "name": "Muddy's Top 10",
      "owner": {"id": "317vyyng6qvtj4ibanvybny4zkvq"},
      "public": true,
      "tracks": {"total": 10}
    }
  ]
}
```

**Used By:** Playlist lookup (find or create)  
**Location:** `music_providers.py:get_user_playlists()`  
**Scopes Required:** `playlist-read-private`  
**Notes:** 
- Returns up to 50 playlists per request
- Includes both owned and followed playlists
- We filter by name="Muddy's Top 10" and owner=current_user

---

### Create Playlist
**Method:** `POST`  
**Endpoint:** `https://api.spotify.com/v1/me/playlists`  
**Purpose:** Create new "Muddy's Top 10" playlist if it doesn't exist

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Body:**
```json
{
  "name": "Muddy's Top 10",
  "description": "Top 10 most played tracks at Muddy's Music Cafe. Updated weekly...",
  "public": true
}
```

**Response:** `201 Created`
```json
{
  "id": "7Dzb7magODhR205xKnbSoC",
  "name": "Muddy's Top 10",
  "owner": {"id": "317vyyng6qvtj4ibanvybny4zkvq"},
  "public": true,
  "uri": "spotify:playlist:7Dzb7magODhR205xKnbSoC"
}
```

**Used By:** First-time playlist creation  
**Location:** `music_providers.py:create_playlist()`  
**Scopes Required:** `playlist-modify-public` or `playlist-modify-private`  
**Notes:** 
- Only called if playlist doesn't already exist
- Returns the new playlist ID
- Playlist starts empty (no tracks)

---

### Replace Playlist Tracks
**Method:** `PUT`  
**Endpoint:** `https://api.spotify.com/v1/playlists/{playlist_id}/tracks`  
**Purpose:** Replace all tracks in playlist (clears old, adds new)

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Body:**
```json
{
  "uris": [
    "spotify:track:4iV5W9uYEdYUVa79Axb7Rh",
    "spotify:track:1301WleyT98MSxVHPZCA6M"
  ]
}
```

**Response:** `200 OK` or `201 Created`
```json
{
  "snapshot_id": "AAAABpJ3..."
}
```

**Used By:** Weekly playlist update  
**Location:** `music_providers.py:replace_playlist_tracks()`  
**Scopes Required:** `playlist-modify-public` or `playlist-modify-private`  
**Notes:** 
- **Replaces ALL tracks** in one operation (clears then adds)
- Maximum 100 tracks per request
- More efficient than delete + add
- Returns snapshot ID for versioning

---

### Add Tracks to Playlist
**Method:** `POST`  
**Endpoint:** `https://api.spotify.com/v1/playlists/{playlist_id}/items`  
**Purpose:** Add tracks to playlist (append, don't replace)

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Body:**
```json
{
  "uris": [
    "spotify:track:4iV5W9uYEdYUVa79Axb7Rh",
    "spotify:track:1301WleyT98MSxVHPZCA6M"
  ]
}
```

**Response:** `201 Created`
```json
{
  "snapshot_id": "AAAABpJ3..."
}
```

**Used By:** Legacy code (replaced by replace_playlist_tracks)  
**Location:** `music_providers.py:add_tracks_to_playlist()`  
**Scopes Required:** `playlist-modify-public` or `playlist-modify-private`  
**Notes:** 
- **IMPORTANT:** Endpoint is `/items` not `/tracks`!
- Appends tracks (doesn't replace)
- Maximum 100 tracks per request
- Can specify position with `position` parameter

---

### Upload Playlist Cover
**Method:** `PUT`  
**Endpoint:** `https://api.spotify.com/v1/playlists/{playlist_id}/images`  
**Purpose:** Upload custom cover image for playlist

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: image/jpeg
```

**Body:** (Raw base64-encoded JPEG data)
```
/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQN...
```

**Response:** `202 Accepted`

**Used By:** Playlist branding with Muddy's logo  
**Location:** `music_providers.py:upload_playlist_cover()`  
**Scopes Required:** `ugc-image-upload`, `playlist-modify-public` or `playlist-modify-private`  
**Notes:** 
- Image must be base64-encoded JPEG
- Maximum size: 256 KB
- Image is resized/cropped by Spotify to square format
- 202 response means accepted (not 200 or 201)

---

## OAuth Flow

### Authorization URL
**Redirect user to:**
```
https://accounts.spotify.com/authorize?
  client_id={client_id}&
  response_type=code&
  redirect_uri={redirect_uri}&
  scope=playlist-modify-public playlist-modify-private ugc-image-upload&
  code_challenge_method=S256&
  code_challenge={code_challenge}&
  state={state}
```

**Purpose:** User authorizes app with required scopes  
**Used By:** Admin panel "Connect Spotify" button  
**Location:** `src/api/app.py:spotify_connect()`  

**Scopes Used:**
- `playlist-modify-public` - Create/modify public playlists
- `playlist-modify-private` - Create/modify private playlists
- `ugc-image-upload` - Upload custom playlist cover images

**Security:** Uses PKCE (Proof Key for Code Exchange) for security

---

### Token Exchange
**Method:** `POST`  
**Endpoint:** `https://accounts.spotify.com/api/token`  
**Purpose:** Exchange authorization code for refresh token

**Headers:**
```
Authorization: Basic {base64(client_id:client_secret)}
Content-Type: application/x-www-form-urlencoded
```

**Body:**
```
grant_type=authorization_code&
code={authorization_code}&
redirect_uri={redirect_uri}&
code_verifier={code_verifier}
```

**Response:** `200 OK`
```json
{
  "access_token": "BQD...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "AQD...",
  "scope": "playlist-modify-public playlist-modify-private ugc-image-upload"
}
```

**Used By:** OAuth callback handler  
**Location:** `src/api/app.py:spotify_callback()`  
**Notes:** 
- Only called once during authorization
- Refresh token stored in AWS Secrets Manager
- Access token discarded (refreshed as needed)

---

## API Call Flow for Playlist Generation

### Complete Flow (Weekly Automation)

1. **Get Access Token** (`POST /api/token`)
   - Use refresh token from Secrets Manager
   - Get fresh access token (valid 1 hour)

2. **Get Current User** (`GET /me`)
   - Validate token
   - Get user ID for playlist operations

3. **Get User's Playlists** (`GET /me/playlists`)
   - Search for existing "Muddy's Top 10"
   - Check if we own it

4. **Create Playlist** (if not exists) (`POST /me/playlists`)
   - Create "Muddy's Top 10" playlist
   - Set public, add description

5. **Search for Tracks** (`GET /search`) × 10
   - For each Top 10 track
   - Find Spotify URI by artist + title

6. **Replace Tracks** (`PUT /playlists/{id}/tracks`)
   - Clear old tracks
   - Add new Top 10 tracks
   - All in one operation

7. **Upload Cover** (`PUT /playlists/{id}/images`)
   - Upload Muddy's logo
   - Base64 JPEG, max 256KB

---

## Error Handling

### Common Error Codes

**401 Unauthorized**
- Token expired or invalid
- Solution: Refresh token

**403 Forbidden**
- Missing required scope
- Wrong endpoint (e.g., `/tracks` instead of `/items`)
- Solution: Reconnect with correct scopes

**404 Not Found**
- Playlist doesn't exist
- Invalid playlist ID
- Solution: Create new playlist

**429 Too Many Requests**
- Rate limit exceeded
- Solution: Wait for Retry-After seconds

**500/502/503 Server Error**
- Spotify API issue
- Solution: Retry with exponential backoff

---

## Rate Limits

### Spotify API Limits
- **Rolling window:** 30 seconds
- **Recommended:** < 1 request per second average
- **429 Response:** Includes `Retry-After` header (seconds)

### Our Implementation
- Track rate limits per provider (class-level `_rate_limited_until`)
- Honor `Retry-After` header
- Skip Spotify during cooldown period
- Fallback to MusicBrainz when rate limited

---

## Environment Variables

```bash
SPOTIFY_CLIENT_ID=abc123...          # App client ID
SPOTIFY_CLIENT_SECRET=xyz789...      # App client secret
SPOTIFY_REFRESH_TOKEN_SECRET=arn:... # Secrets Manager ARN
```

---

## Files Reference

**Spotify Provider:** `layers/common/music_providers.py`
- All API call implementations
- Token management
- Rate limiting

**Playlist Generator:** `src/playlist-generator/app.py`
- Weekly automation logic
- Find/create/update flow
- Logo upload

**OAuth Handler:** `src/api/app.py`
- Authorization flow
- Callback handling
- Token storage

**Logo:** `layers/common/logo.jpg`
- 640×640 JPEG
- < 256KB
- Deployed with Lambda layer

---

## Testing

### Manual Playlist Generation
```bash
# Via admin panel
1. Login to admin panel
2. Go to Spotify tab
3. Click "Generate Playlist Now"

# Via AWS CLI
aws lambda invoke \
  --function-name muddys-top10-playlist-generator \
  --payload '{}' \
  /tmp/output.json
```

### Check Logs
```bash
aws logs tail /aws/lambda/muddys-top10-playlist-generator --follow
```

### Verify Playlist
```
https://open.spotify.com/playlist/{playlist_id}
```

---

## References

- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api)
- [OAuth 2.0 Authorization](https://developer.spotify.com/documentation/web-api/concepts/authorization)
- [Rate Limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits)
- [API Reference](https://developer.spotify.com/documentation/web-api/reference)
