"""
Music metadata provider implementations
"""
import json
import urllib3
from urllib.parse import quote
from typing import List, Optional, Dict
from dataclasses import dataclass
from track_normalizer import score_artist_match, score_title_match, normalize_string

# Disable SSL warnings for HTTP client
urllib3.disable_warnings()

# Configure retry with minimal backoff to avoid long freezes
retry = urllib3.Retry(
    total=2,  # Only retry twice
    backoff_factor=0.3,  # Short backoff
    status_forcelist=[429, 500, 502, 503, 504],  # Only retry on these statuses
    raise_on_status=False  # Don't raise exceptions, just return response
)
http = urllib3.PoolManager(retries=retry)


@dataclass
class TrackMatch:
    """Track match result from provider"""
    source: str
    source_id: str
    artist: str
    title: str
    release: Optional[str] = None
    artist_score: float = 0.0
    title_score: float = 0.0
    total_score: float = 0.0
    confidence: str = 'low'  # low, medium, high
    raw_data: Optional[dict] = None


class MusicBrainzProvider:
    """MusicBrainz API provider"""

    BASE_URL = 'https://musicbrainz.org/ws/2'
    USER_AGENT = 'MuddysTop10/1.0 (https://github.com/yourusername/muddys-top10)'

    def search(self, artist: Optional[str], title: str) -> List[Dict]:
        """Search MusicBrainz for tracks"""
        try:
            # Build query
            if artist:
                query = f'artist:"{artist}" AND recording:"{title}"'
            else:
                query = f'recording:"{title}"'

            url = f'{self.BASE_URL}/recording/'
            params = {
                'query': query,
                'fmt': 'json',
                'limit': 10
            }

            query_string = '&'.join(f'{k}={quote(str(v))}' for k, v in params.items())
            full_url = f'{url}?{query_string}'

            response = http.request(
                'GET',
                full_url,
                headers={
                    'User-Agent': self.USER_AGENT,
                    'Accept': 'application/json'
                },
                timeout=10.0
            )

            if response.status != 200:
                error_body = response.data.decode('utf-8') if response.data else 'No response body'
                print(f"MusicBrainz error: HTTP {response.status}")
                print(f"  URL: {full_url[:100]}...")
                print(f"  Response: {error_body[:200]}")

                # If 503, service is overloaded
                if response.status == 503:
                    print("  Service temporarily unavailable")

                return []

            data = json.loads(response.data.decode('utf-8'))
            return data.get('recordings', [])

        except Exception as e:
            print(f"MusicBrainz search error: {e}")
            print(f"  Query: {query[:100] if 'query' in locals() else 'N/A'}")
            return []

    def parse_results(self, results: List[Dict], input_artist: Optional[str], input_title: str) -> List[TrackMatch]:
        """Parse MusicBrainz results into TrackMatch objects"""
        matches = []

        for recording in results:
            try:
                # Get artist name (first credited artist)
                artist_name = None
                if 'artist-credit' in recording and recording['artist-credit']:
                    artist_name = recording['artist-credit'][0].get('name')

                # Get title
                title = recording.get('title')

                if not title:
                    continue

                # Get release info if available
                release = None
                if 'releases' in recording and recording['releases']:
                    release = recording['releases'][0].get('title')

                # Score the match
                artist_score = 0.0
                if input_artist and artist_name:
                    artist_score = score_artist_match(input_artist, artist_name)
                elif not input_artist:
                    # No artist input, can't penalize
                    artist_score = 0.5

                title_score = score_title_match(input_title, title)

                # Weighted total score
                total_score = (artist_score * 0.4) + (title_score * 0.5)

                # Popularity bonus (MusicBrainz doesn't provide this, use position as proxy)
                popularity_bonus = (10 - len(matches)) * 0.01
                total_score += popularity_bonus

                # Determine confidence
                confidence = 'low'
                if artist_score > 0.85 and title_score > 0.85:
                    confidence = 'high'
                elif artist_score > 0.7 and title_score > 0.7:
                    confidence = 'medium'
                # Special case: Perfect title match with reasonable artist score
                elif title_score >= 0.95 and artist_score > 0.3 and total_score > 0.55:
                    confidence = 'medium'

                matches.append(TrackMatch(
                    source='musicbrainz',
                    source_id=recording.get('id', ''),
                    artist=artist_name or 'Unknown',
                    title=title,
                    release=release,
                    artist_score=artist_score,
                    title_score=title_score,
                    total_score=total_score,
                    confidence=confidence,
                    raw_data=recording
                ))

            except Exception as e:
                print(f"Error parsing MusicBrainz result: {e}")
                continue

        return sorted(matches, key=lambda x: x.total_score, reverse=True)


class SpotifyProvider:
    """Spotify API provider (requires client credentials)"""

    BASE_URL = 'https://api.spotify.com/v1'
    TOKEN_URL = 'https://accounts.spotify.com/api/token'

    # Class-level rate limit tracking (shared across all instances in same Lambda execution)
    _rate_limited_until = 0  # Unix timestamp when rate limit expires

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, refresh_token: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None

    def get_access_token(self) -> Optional[str]:
        """Get Spotify access token using client credentials flow or refresh token"""
        if not self.client_id or not self.client_secret:
            return None

        try:
            import base64

            credentials = f"{self.client_id}:{self.client_secret}"
            credentials_b64 = base64.b64encode(credentials.encode()).decode()

            # Use refresh token if available (for playlist creation)
            if self.refresh_token:
                print(f"Using refresh token for OAuth (length: {len(self.refresh_token)})")
                body = f'grant_type=refresh_token&refresh_token={self.refresh_token}'
            else:
                # Fall back to client credentials (for search only)
                print("Using client credentials flow (read-only access)")
                body = 'grant_type=client_credentials'

            response = http.request(
                'POST',
                self.TOKEN_URL,
                headers={
                    'Authorization': f'Basic {credentials_b64}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body=body,
                timeout=10.0
            )

            if response.status != 200:
                error_body = response.data.decode('utf-8') if response.data else 'No response body'
                print(f"Spotify token error: HTTP {response.status}")
                print(f"  Grant type: {'refresh_token' if self.refresh_token else 'client_credentials'}")
                print(f"  Response: {error_body}")
                return None

            data = json.loads(response.data.decode('utf-8'))
            self.access_token = data.get('access_token')
            scopes = data.get('scope', '')
            token_preview = self.access_token[:20] if self.access_token else "None"
            print(f"Successfully obtained access token: {token_preview}... (length: {len(self.access_token) if self.access_token else 0})")
            print(f"  Using refresh_token: {bool(self.refresh_token)}")
            print(f"  Scopes granted: {scopes}")
            return self.access_token

        except Exception as e:
            print(f"Spotify token error: {e}")
            import traceback
            print(f"  Details: {traceback.format_exc()[:300]}")
            return None

    def search(self, artist: Optional[str], title: str) -> List[Dict]:
        """Search Spotify for tracks"""
        # Check if we're in cooldown period
        import time
        current_time = int(time.time())
        if SpotifyProvider._rate_limited_until > current_time:
            cooldown_remaining = SpotifyProvider._rate_limited_until - current_time
            print(f"Spotify rate limited, skipping (cooldown: {cooldown_remaining}s remaining)")
            return []

        if not self.access_token:
            self.access_token = self.get_access_token()

        if not self.access_token:
            print("No Spotify access token available")
            return []

        try:
            # Build query
            if artist:
                query = f'artist:"{artist}" track:"{title}"'
            else:
                query = f'track:"{title}"'

            url = f'{self.BASE_URL}/search'
            params = {
                'q': query,
                'type': 'track',
                'limit': 10
            }

            query_string = '&'.join(f'{k}={quote(str(v))}' for k, v in params.items())
            full_url = f'{url}?{query_string}'

            response = http.request(
                'GET',
                full_url,
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Accept': 'application/json'
                },
                timeout=urllib3.Timeout(connect=5.0, read=5.0)
            )

            if response.status != 200:
                error_body = response.data.decode('utf-8') if response.data else 'No response body'
                print(f"Spotify error: HTTP {response.status}")
                print(f"  URL: {full_url[:100]}...")
                print(f"  Response: {error_body[:200]}")

                # If 401, token might be expired
                if response.status == 401:
                    print("  Token may be expired, attempting refresh...")
                    self.access_token = None

                # If 429, we hit rate limit - set cooldown period
                if response.status == 429:
                    import time
                    retry_after = int(response.headers.get('Retry-After', '60'))
                    SpotifyProvider._rate_limited_until = int(time.time()) + retry_after
                    print(f"  Rate limited. Entering cooldown for {retry_after} seconds")
                    print(f"  Spotify will be skipped until cooldown expires")

                return []

            data = json.loads(response.data.decode('utf-8'))
            return data.get('tracks', {}).get('items', [])

        except Exception as e:
            print(f"Spotify search error: {e}")
            print(f"  Query: {query[:100] if 'query' in locals() else 'N/A'}")
            return []

    def parse_results(self, results: List[Dict], input_artist: Optional[str], input_title: str) -> List[TrackMatch]:
        """Parse Spotify results into TrackMatch objects"""
        matches = []

        for track in results:
            try:
                # Get artist name (first artist)
                artist_name = None
                if 'artists' in track and track['artists']:
                    artist_name = track['artists'][0].get('name')

                # Get title
                title = track.get('name')

                if not title:
                    continue

                # Get album/release info
                release = None
                if 'album' in track:
                    release = track['album'].get('name')

                # Score the match
                artist_score = 0.0
                if input_artist and artist_name:
                    artist_score = score_artist_match(input_artist, artist_name)
                elif not input_artist:
                    artist_score = 0.5

                title_score = score_title_match(input_title, title)

                # Weighted total score
                total_score = (artist_score * 0.4) + (title_score * 0.5)

                # Popularity bonus from Spotify
                popularity = track.get('popularity', 0)
                popularity_bonus = (popularity / 100) * 0.1
                total_score += popularity_bonus

                # Determine confidence
                confidence = 'low'
                if artist_score > 0.85 and title_score > 0.85:
                    confidence = 'high'
                elif artist_score > 0.7 and title_score > 0.7:
                    confidence = 'medium'
                # Special case: Perfect title match with reasonable artist score
                elif title_score >= 0.95 and artist_score > 0.3 and total_score > 0.55:
                    confidence = 'medium'

                matches.append(TrackMatch(
                    source='spotify',
                    source_id=track.get('id', ''),
                    artist=artist_name or 'Unknown',
                    title=title,
                    release=release,
                    artist_score=artist_score,
                    title_score=title_score,
                    total_score=total_score,
                    confidence=confidence,
                    raw_data=track
                ))

            except Exception as e:
                print(f"Error parsing Spotify result: {e}")
                continue

        return sorted(matches, key=lambda x: x.total_score, reverse=True)

    def get_track_uri(self, artist: str, title: str) -> Optional[str]:
        """Search for a track and return its Spotify URI"""
        results = self.search(artist, title)
        if results and len(results) > 0:
            # Return the first result's URI
            track_id = results[0].get('id')
            if track_id:
                return f'spotify:track:{track_id}'
        return None

    def create_playlist(self, user_id: str, name: str, description: str = '', public: bool = True) -> Optional[str]:
        """Create a new playlist and return its ID

        Note: user_id parameter is kept for backwards compatibility but not used.
        The newer /me/playlists endpoint is more reliable and doesn't require user_id.
        """
        if not self.access_token:
            self.access_token = self.get_access_token()

        if not self.access_token:
            print("No Spotify access token available for playlist creation")
            return None

        try:
            # Use /me/playlists instead of /users/{user_id}/playlists
            # This is simpler and more reliable with OAuth tokens
            url = f'{self.BASE_URL}/me/playlists'

            body = json.dumps({
                'name': name,
                'description': description,
                'public': public
            })

            response = http.request(
                'POST',
                url,
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                },
                body=body,
                timeout=urllib3.Timeout(connect=5.0, read=5.0)
            )

            if response.status != 201:
                error_body = response.data.decode('utf-8') if response.data else 'No response body'
                print(f"Spotify create playlist error: HTTP {response.status}")
                print(f"  URL: {url}")
                print(f"  Response: {error_body}")
                return None

            data = json.loads(response.data.decode('utf-8'))
            return data.get('id')

        except Exception as e:
            print(f"Spotify create playlist error: {e}")
            return None

    def check_token_scopes(self):
        """Check what scopes the current token has"""
        if not self.access_token:
            return None

        try:
            # Try to get current user to validate token
            response = http.request(
                'GET',
                'https://api.spotify.com/v1/me',
                headers={'Authorization': f'Bearer {self.access_token}'},
                timeout=5.0
            )
            print(f"Token validation: HTTP {response.status}")
            if response.status == 200:
                data = json.loads(response.data.decode('utf-8'))
                print(f"  Authenticated as: {data.get('id')} ({data.get('display_name')})")
                print(f"  Product: {data.get('product', 'unknown')}")

            # IMPORTANT: Check if we have the refresh_token set
            print(f"  Provider has refresh_token: {bool(self.refresh_token)}")
            if not self.refresh_token:
                print("  WARNING: Using client credentials (read-only) - playlist modification will fail!")

            return response.status == 200
        except Exception as e:
            print(f"Token check error: {e}")
            return False

    def get_user_playlists(self, limit: int = 50) -> List[Dict]:
        """Get current user's playlists"""
        if not self.access_token:
            self.access_token = self.get_access_token()

        if not self.access_token:
            print("No Spotify access token available")
            return []

        try:
            url = f'{self.BASE_URL}/me/playlists?limit={limit}'

            response = http.request(
                'GET',
                url,
                headers={'Authorization': f'Bearer {self.access_token}'},
                timeout=urllib3.Timeout(connect=5.0, read=5.0)
            )

            if response.status != 200:
                error_body = response.data.decode('utf-8') if response.data else 'No response body'
                print(f"Spotify get playlists error: HTTP {response.status}")
                print(f"  Response: {error_body}")
                return []

            data = json.loads(response.data.decode('utf-8'))
            return data.get('items', [])

        except Exception as e:
            print(f"Spotify get playlists error: {e}")
            return []

    def get_playlist_items(self, playlist_id: str) -> List[Dict]:
        """Get all items currently in a playlist"""
        if not self.access_token:
            self.access_token = self.get_access_token()

        if not self.access_token:
            print("No Spotify access token available")
            return []

        try:
            all_items = []
            url = f'{self.BASE_URL}/playlists/{playlist_id}/items?limit=50'

            while url:
                response = http.request(
                    'GET',
                    url,
                    headers={'Authorization': f'Bearer {self.access_token}'},
                    timeout=urllib3.Timeout(connect=5.0, read=5.0)
                )

                if response.status != 200:
                    error_body = response.data.decode('utf-8') if response.data else 'No response body'
                    print(f"Spotify get items error: HTTP {response.status}")
                    print(f"  Response: {error_body}")
                    break

                data = json.loads(response.data.decode('utf-8'))
                items = data.get('items', [])
                all_items.extend(items)

                # Check for pagination
                url = data.get('next')

            return all_items

        except Exception as e:
            print(f"Spotify get items error: {e}")
            return []

    def remove_playlist_items(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Remove items from a playlist"""
        if not self.access_token:
            self.access_token = self.get_access_token()

        if not self.access_token:
            print("No Spotify access token available")
            return False

        try:
            # DELETE /playlists/{id}/items - max 100 items per request
            url = f'{self.BASE_URL}/playlists/{playlist_id}/items'

            # Process in batches of 100
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i:i+100]

                # Format as array of objects with uri field
                items = [{'uri': uri} for uri in batch]
                body = json.dumps({'items': items})

                print(f"Removing {len(batch)} items from playlist")

                response = http.request(
                    'DELETE',
                    url,
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json'
                    },
                    body=body,
                    timeout=urllib3.Timeout(connect=5.0, read=5.0)
                )

                if response.status != 200:
                    error_body = response.data.decode('utf-8') if response.data else 'No response body'
                    print(f"Spotify remove items error: HTTP {response.status}")
                    print(f"  Response: {error_body}")
                    return False

            return True

        except Exception as e:
            print(f"Spotify remove items error: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def replace_playlist_tracks(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Replace all tracks in a playlist (get, delete, add)"""
        print(f"Replacing all tracks in playlist {playlist_id}")
        print(f"  New track count: {len(track_uris)}")

        # Step 1: Get existing items
        print("Step 1: Getting existing playlist items...")
        existing_items = self.get_playlist_items(playlist_id)
        print(f"  Found {len(existing_items)} existing items")

        # Step 2: Remove existing items if any
        if existing_items:
            print("Step 2: Removing existing items...")
            existing_uris = []
            for item in existing_items:
                track = item.get('track')
                if track and track.get('uri'):
                    existing_uris.append(track['uri'])

            if existing_uris:
                success = self.remove_playlist_items(playlist_id, existing_uris)
                if not success:
                    print("  Failed to remove existing items")
                    return False
                print(f"  Removed {len(existing_uris)} items")
        else:
            print("Step 2: No existing items to remove")

        # Step 3: Add new tracks
        print("Step 3: Adding new tracks...")
        success = self.add_tracks_to_playlist(playlist_id, track_uris)
        if not success:
            print("  Failed to add new tracks")
            return False

        print(f"✓ Successfully replaced playlist with {len(track_uris)} tracks")
        return True

    def upload_playlist_cover(self, playlist_id: str, image_base64: str) -> bool:
        """Upload custom playlist cover image"""
        if not self.access_token:
            self.access_token = self.get_access_token()

        if not self.access_token:
            print("No Spotify access token available")
            return False

        try:
            url = f'{self.BASE_URL}/playlists/{playlist_id}/images'

            print(f"Uploading cover image to playlist {playlist_id}")
            print(f"  Image size: {len(image_base64)} bytes")

            response = http.request(
                'PUT',
                url,
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'image/jpeg'
                },
                body=image_base64,
                timeout=urllib3.Timeout(connect=5.0, read=10.0)
            )

            if response.status != 202:
                error_body = response.data.decode('utf-8') if response.data else 'No response body'
                print(f"Spotify upload cover error: HTTP {response.status}")
                print(f"  Response: {error_body}")
                return False

            print("Cover image uploaded successfully")
            return True

        except Exception as e:
            print(f"Spotify upload cover error: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Add tracks to a playlist (max 100 tracks per request)"""
        print(f"add_tracks_to_playlist called with playlist_id={playlist_id}")
        print(f"  self.refresh_token is set: {bool(self.refresh_token)}")
        print(f"  self.access_token is set: {bool(self.access_token)}")

        if not self.access_token:
            print("  Getting new access token...")
            self.access_token = self.get_access_token()

        if not self.access_token:
            print("No Spotify access token available for adding tracks")
            return False

        # Check token validity
        self.check_token_scopes()

        try:
            # Use /items endpoint (not /tracks) per Spotify API docs
            url = f'{self.BASE_URL}/playlists/{playlist_id}/items'

            # Spotify limits to 100 tracks per request
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i:i+100]

                # Some Spotify APIs prefer 'uris' as a JSON array in the body
                # Others work better with query parameters
                # Let's try the most standard format
                body = json.dumps({'uris': batch})

                print(f"Adding tracks to playlist {playlist_id}")
                print(f"  URL: {url}")
                print(f"  Track URIs: {batch}")
                print(f"  Token length: {len(self.access_token)}")

                response = http.request(
                    'POST',
                    url,
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json'
                    },
                    body=body,
                    timeout=urllib3.Timeout(connect=5.0, read=5.0)
                )

                print(f"Response status: {response.status}")

                # Accept both 200 and 201 as success
                if response.status not in [200, 201]:
                    error_body = response.data.decode('utf-8') if response.data else 'No response body'
                    print(f"Spotify add tracks error: HTTP {response.status}")
                    print(f"  Response: {error_body}")
                    print(f"  Request body: {body[:500]}")
                    return False

            return True

        except Exception as e:
            print(f"Spotify add tracks error: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def get_current_user(self) -> Optional[Dict]:
        """Get current user profile (requires user token, not client credentials)"""
        if not self.access_token:
            self.access_token = self.get_access_token()

        if not self.access_token:
            print("No Spotify access token available")
            return None

        try:
            url = f'{self.BASE_URL}/me'

            response = http.request(
                'GET',
                url,
                headers={
                    'Authorization': f'Bearer {self.access_token}'
                },
                timeout=urllib3.Timeout(connect=5.0, read=5.0)
            )

            if response.status != 200:
                error_body = response.data.decode('utf-8') if response.data else 'No response body'
                print(f"Spotify get user error: HTTP {response.status}")
                print(f"  Response: {error_body[:200]}")
                return None

            data = json.loads(response.data.decode('utf-8'))
            return data

        except Exception as e:
            print(f"Spotify get user error: {e}")
            return None


def search_all_providers(artist: Optional[str], title: str,
                         spotify_client_id: Optional[str] = None,
                         spotify_client_secret: Optional[str] = None,
                         musicbrainz_enabled: bool = True,
                         spotify_enabled: bool = True) -> List[TrackMatch]:
    """Search all available providers and return ranked results"""
    all_matches = []

    if musicbrainz_enabled:
        try:
            print(f"Searching MusicBrainz for: {artist} - {title}")
            mb_provider = MusicBrainzProvider()
            mb_results = mb_provider.search(artist, title)
            if mb_results:
                all_matches.extend(mb_provider.parse_results(mb_results, artist, title))
                print(f"MusicBrainz returned {len(mb_results)} results")
            else:
                print("MusicBrainz returned no results")
        except Exception as e:
            print(f"MusicBrainz search failed: {e}")
            # Continue to next provider
    else:
        print("Skipping MusicBrainz because the verification source is disabled")

    # Search Spotify if credentials available and not rate limited
    if spotify_enabled and spotify_client_id and spotify_client_secret:
        import time
        current_time = int(time.time())

        # Check if we're in cooldown before creating provider
        if SpotifyProvider._rate_limited_until > current_time:
            cooldown_remaining = SpotifyProvider._rate_limited_until - current_time
            print(f"Skipping Spotify (rate limit cooldown: {cooldown_remaining}s remaining)")
        else:
            try:
                print(f"Searching Spotify for: {artist} - {title}")
                spotify_provider = SpotifyProvider(spotify_client_id, spotify_client_secret)
                spotify_results = spotify_provider.search(artist, title)
                if spotify_results:
                    all_matches.extend(spotify_provider.parse_results(spotify_results, artist, title))
                    print(f"Spotify returned {len(spotify_results)} results")
                else:
                    print("Spotify returned no results")
            except Exception as e:
                print(f"Spotify search failed: {e}")
                # Continue with MusicBrainz results if available
    elif not spotify_enabled:
        print("Skipping Spotify because the verification source is disabled")

    # Sort by total score
    return sorted(all_matches, key=lambda x: x.total_score, reverse=True)
