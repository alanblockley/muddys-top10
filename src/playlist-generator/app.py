"""
Playlist Generator Lambda
Generates a weekly Spotify playlist with the current Top 10 tracks
Runs every Saturday at 2am PST (2 hours before chart reset)
"""
import os
import json
import boto3
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from boto3.dynamodb.conditions import Key
from common import get_env, get_timestamp, get_chart_counting_window, format_timestamp
from music_providers import SpotifyProvider

dynamodb = boto3.resource('dynamodb')
tracks_table = dynamodb.Table(get_env('TRACKS_TABLE'))
config_table = dynamodb.Table(get_env('CONFIG_TABLE'))
chart_history_table = dynamodb.Table(get_env('CHART_HISTORY_TABLE'))
secrets_client = boto3.client('secretsmanager')


def get_config_value(key):
    """Get configuration value from DynamoDB"""
    try:
        response = config_table.get_item(Key={'configKey': key})
        return response.get('Item', {}).get('value')
    except Exception as e:
        print(f"Error getting config {key}: {e}")
        return None


def should_filter_track(track_name, filter_patterns):
    """Check if track should be filtered from Top 10"""
    if not filter_patterns:
        return False

    import re
    for pattern in filter_patterns:
        try:
            if re.search(pattern, track_name, re.IGNORECASE):
                return True
        except re.error:
            # Invalid regex, try exact match
            if pattern.lower() in track_name.lower():
                return True

    return False


def get_top10_tracks():
    """Get current Top 10 tracks (MUST match API logic exactly)"""
    try:
        chart_context = get_chart_context()
        chart_timestamp = chart_context['week_start_timestamp']
        current_week_end = chart_context['week_end_timestamp']
        filter_patterns = chart_context['filter_patterns']

        print(f"Fetching Top 10 for week: {datetime.fromtimestamp(chart_timestamp, tz=ZoneInfo('America/Los_Angeles'))} to {datetime.fromtimestamp(current_week_end, tz=ZoneInfo('America/Los_Angeles'))}")

        track_counts, track_info_by_name, total_tracks = get_track_counts_between(
            chart_timestamp,
            current_week_end,
            filter_patterns
        )
        print(f"Found {total_tracks} total tracks this week")

        print(f"After filtering: {len(track_counts)} unique tracks")

        # Get top 10
        top10 = []
        for track_name, count in track_counts.most_common(10):
            # Get artist and title from first occurrence
            track_info = track_info_by_name.get(track_name)

            artist = track_info.get('artist', '') if track_info else ''
            title = track_info.get('title', '') if track_info else ''

            # If we don't have artist/title, try to parse from track name
            if not artist or not title:
                if ' - ' in track_name:
                    parts = track_name.split(' - ', 1)
                    artist = parts[0].strip()
                    title = parts[1].strip()
                else:
                    artist = 'Unknown'
                    title = track_name

            top10.append({
                'rank': len(top10) + 1,
                'artist': artist,
                'title': title,
                'canonical_track': track_name,
                'plays': count
            })

        top10_summary = [f"{t['rank']}. {t['artist']} - {t['title']} ({t['plays']} plays)" for t in top10]
        print(f"Top 10: {top10_summary}")

        previous_counts, _, _ = get_track_counts_between(
            chart_context['previous_week_start_timestamp'],
            chart_context['previous_week_count_end_timestamp'],
            filter_patterns
        )
        save_top10_snapshot(chart_context, top10, track_counts, previous_counts)

        return top10

    except Exception as e:
        print(f"Error getting Top 10: {e}")
        import traceback
        print(traceback.format_exc())
        return []


def get_chart_context():
    config = normalize_chart_config(get_config_value('chart_generation'))

    filter_config = get_config_value('top10_filters')
    filter_patterns = filter_config if filter_config else []

    current_time = get_timestamp()
    chart_window = get_chart_counting_window(current_time, config)

    return {
        'generated_at_timestamp': current_time,
        'week_start_timestamp': chart_window['week_start_timestamp'],
        'week_end_timestamp': chart_window['week_count_end_timestamp'],
        'week_count_end_timestamp': chart_window['week_count_end_timestamp'],
        'week_reset_end_timestamp': chart_window['week_reset_end_timestamp'],
        'previous_week_start_timestamp': chart_window['previous_week_start_timestamp'],
        'previous_week_count_end_timestamp': chart_window['previous_week_count_end_timestamp'],
        'previous_week_reset_end_timestamp': chart_window['previous_week_reset_end_timestamp'],
        'freeze_window': chart_window,
        'chart_config': config,
        'filter_patterns': filter_patterns
    }


def normalize_chart_config(config):
    config = config if isinstance(config, dict) else {}
    valid_days = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}
    reset_day = str(config.get('day', 'monday')).lower()
    if reset_day not in valid_days:
        reset_day = 'monday'
    reset_hour = int(config.get('hour') if config.get('hour') is not None else 0)
    campaign_day, campaign_hour = default_campaign_time(reset_day, reset_hour)
    configured_campaign_day = str(config.get('campaign_day', campaign_day)).lower()
    if configured_campaign_day not in valid_days:
        configured_campaign_day = campaign_day

    return {
        'day': reset_day,
        'hour': reset_hour,
        'campaign_generation_enabled': config.get('campaign_generation_enabled', True),
        'campaign_day': configured_campaign_day,
        'campaign_hour': int(config.get('campaign_hour') if config.get('campaign_hour') is not None else campaign_hour),
        'freeze_enabled': config.get('freeze_enabled', True)
    }


def default_campaign_time(reset_day, reset_hour):
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    campaign_hour = reset_hour - 2
    if campaign_hour >= 0:
        return reset_day, campaign_hour
    previous_day = days[(days.index(reset_day) - 1) % len(days)]
    return previous_day, campaign_hour + 24


def get_track_counts_between(start_ts, end_ts, filter_patterns):
    track_counts = Counter()
    track_info_by_name = {}
    total_tracks = 0
    query_args = {
        'IndexName': 'timestamp-index',
        'KeyConditionExpression': Key('pk').eq('TRACK') & Key('timestamp').between(start_ts, end_ts)
    }

    while True:
        response = tracks_table.query(**query_args)
        items = response.get('Items', [])
        total_tracks += len(items)

        for track in items:
            track_name = track.get('canonical_track') or track['track']
            if should_filter_track(track_name, filter_patterns):
                print(f"Filtered out: {track_name}")
                continue

            track_counts[track_name] += 1
            track_info_by_name.setdefault(track_name, track)

        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        query_args['ExclusiveStartKey'] = last_key

    return track_counts, track_info_by_name, total_tracks


def save_top10_snapshot(chart_context, top10_tracks, current_counts, previous_counts):
    previous_ranks = {
        track: rank
        for rank, (track, _) in enumerate(previous_counts.most_common(), 1)
    }

    history_top10 = []
    for track in top10_tracks:
        track_name = track['canonical_track']
        rank = track['rank']
        previous_rank = previous_ranks.get(track_name)
        if previous_rank is None:
            movement = 'new'
        elif previous_rank > rank:
            movement = 'up'
        elif previous_rank < rank:
            movement = 'down'
        else:
            movement = 'same'

        history_top10.append({
            'rank': rank,
            'track': track_name,
            'artist': track.get('artist'),
            'title': track.get('title'),
            'play_count': track['plays'],
            'previous_rank': previous_rank,
            'movement': movement,
            'movement_delta': (previous_rank - rank) if previous_rank else None
        })

    week_start = chart_context['week_start_timestamp']
    week_end = chart_context['week_end_timestamp']
    previous_week_start = chart_context['previous_week_start_timestamp']
    previous_week_count_end = chart_context['previous_week_count_end_timestamp']
    week_id = chart_week_id(week_start)
    freeze_window = chart_context.get('freeze_window', {})

    chart_history_table.put_item(Item={
        'pk': 'TOP10_HISTORY',
        'sk': f'WEEK#{week_id}',
        'week_id': week_id,
        'snapshot_type': 'weekly_top10',
        'week_start_timestamp': week_start,
        'week_end_timestamp': week_end,
        'week_count_end_timestamp': chart_context['week_count_end_timestamp'],
        'week_reset_end_timestamp': chart_context['week_reset_end_timestamp'],
        'previous_week_start_timestamp': previous_week_start,
        'previous_week_count_end_timestamp': previous_week_count_end,
        'previous_week_reset_end_timestamp': chart_context['previous_week_reset_end_timestamp'],
        'generated_at_timestamp': chart_context['generated_at_timestamp'],
        'chart_config': chart_context['chart_config'],
        'filter_patterns': chart_context['filter_patterns'],
        'top10': history_top10,
        'summary': {
            'total_plays': sum(current_counts.values()),
            'unique_tracks': len(current_counts),
            'previous_total_plays': sum(previous_counts.values()),
            'previous_unique_tracks': len(previous_counts)
        },
        'chart_date': format_timestamp(week_start),
        'week_start': format_timestamp(week_start),
        'week_end': format_timestamp(week_end),
        'week_count_end': format_timestamp(chart_context['week_count_end_timestamp']),
        'week_reset_end': format_timestamp(chart_context['week_reset_end_timestamp']),
        'previous_week_start': format_timestamp(previous_week_start),
        'previous_week_end': format_timestamp(previous_week_count_end),
        'previous_week_count_end': format_timestamp(previous_week_count_end),
        'previous_week_reset_end': format_timestamp(chart_context['previous_week_reset_end_timestamp']),
        'freeze_window': {
            'enabled': chart_context['chart_config'].get('freeze_enabled', True),
            'start_timestamp': freeze_window.get('freeze_start_timestamp'),
            'end_timestamp': freeze_window.get('freeze_end_timestamp'),
            'start': format_timestamp(freeze_window.get('freeze_start_timestamp')) if freeze_window.get('freeze_start_timestamp') else None,
            'end': format_timestamp(freeze_window.get('freeze_end_timestamp')) if freeze_window.get('freeze_end_timestamp') else None,
            'active': freeze_window.get('is_freeze_window', False)
        }
    })


def chart_week_id(timestamp):
    chart_tz = ZoneInfo('America/Los_Angeles')
    return datetime.fromtimestamp(timestamp, tz=chart_tz).strftime('%Y-%m-%d')


def get_spotify_refresh_token():
    """Get Spotify refresh token from Secrets Manager"""
    try:
        secret_name = os.environ.get('SPOTIFY_REFRESH_TOKEN_SECRET')
        if not secret_name:
            print("No SPOTIFY_REFRESH_TOKEN_SECRET environment variable")
            return None

        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response['SecretString'])
        return secret_data.get('refresh_token')

    except Exception as e:
        print(f"Error getting refresh token: {e}")
        import traceback
        print(traceback.format_exc())
        return None


def get_logo_base64():
    """Get Muddy's logo as base64 JPEG"""
    try:
        import os
        import base64

        # Logo is in the Lambda layer at /opt/python/logo.jpg
        logo_path = '/opt/python/logo.jpg'

        if not os.path.exists(logo_path):
            print(f"Logo not found at {logo_path}")
            return None

        with open(logo_path, 'rb') as f:
            image_data = f.read()

        # Check size (max 256KB for Spotify)
        size_kb = len(image_data) / 1024
        print(f"Logo size: {size_kb:.1f} KB")

        if len(image_data) > 256 * 1024:
            print(f"Logo too large: {size_kb:.1f} KB (max 256KB)")
            return None

        # Encode to base64 (Spotify expects the raw base64 string, not a data URI)
        return base64.b64encode(image_data).decode('utf-8')

    except Exception as e:
        print(f"Error loading logo: {e}")
        import traceback
        print(traceback.format_exc())
        return None


def create_playlist(spotify_provider, top10_tracks):
    """Create or update Spotify playlist with Top 10 tracks"""
    try:
        # Get current user
        user = spotify_provider.get_current_user()
        if not user:
            print("Failed to get Spotify user")
            return None

        user_id = user.get('id')
        print(f"User: {user_id}")

        # Fixed playlist name (no date)
        playlist_name = "Muddy's Top 10"
        pst = ZoneInfo('America/Los_Angeles')
        now = datetime.now(pst)
        playlist_description = f"Top 10 most played tracks at Muddy's Music Cafe. Updated weekly every Saturday. Last updated: {now.strftime('%B %d, %Y')}. Generated automatically from customer requests and DJ playout."

        # Check if playlist already exists
        print("Checking for existing playlist...")
        existing_playlists = spotify_provider.get_user_playlists(limit=50)
        existing_playlist_id = None

        for playlist in existing_playlists:
            if playlist.get('name') == playlist_name and playlist.get('owner', {}).get('id') == user_id:
                existing_playlist_id = playlist.get('id')
                print(f"Found existing playlist: {existing_playlist_id}")
                break

        # Create or update playlist
        if existing_playlist_id:
            playlist_id = existing_playlist_id
            print(f"Updating existing playlist: {playlist_id}")
        else:
            print("Creating new playlist...")
            playlist_id = spotify_provider.create_playlist(
                user_id=user_id,
                name=playlist_name,
                description=playlist_description,
                public=True
            )

        if not playlist_id:
            print("Failed to create playlist")
            return None

        print(f"Created playlist: {playlist_id}")

        # Search for tracks and collect URIs
        track_uris = []
        for track in top10_tracks:
            artist = track['artist']
            title = track['title']

            print(f"Searching for: {artist} - {title}")
            uri = spotify_provider.get_track_uri(artist, title)

            if uri:
                track_uris.append(uri)
                print(f"  Found: {uri}")
            else:
                print(f"  Not found on Spotify")

        if not track_uris:
            print("No tracks found on Spotify")
            return playlist_id

        # Replace all tracks in playlist (clears and adds)
        print(f"Replacing playlist tracks with {len(track_uris)} new tracks")
        success = spotify_provider.replace_playlist_tracks(playlist_id, track_uris)

        if not success:
            print("Failed to replace tracks in playlist")
            return None

        # Upload cover image
        print("Uploading playlist cover image...")
        logo_base64 = get_logo_base64()
        if logo_base64:
            spotify_provider.upload_playlist_cover(playlist_id, logo_base64)
        else:
            print("Skipping cover image upload (logo not available)")

        print(f"Successfully updated playlist with {len(track_uris)} tracks")
        return playlist_id

    except Exception as e:
        print(f"Error creating playlist: {e}")
        import traceback
        print(traceback.format_exc())
        return None


def lambda_handler(event, context):
    """Main Lambda handler"""
    try:
        print("Starting playlist generation")
        print(f"Event: {json.dumps(event)}")

        spotify_playlists_enabled = os.environ.get(
            'ENABLE_SPOTIFY_PLAYLISTS',
            os.environ.get('ENABLE_SPOTIFY', 'false')
        ).lower() == 'true'
        if not spotify_playlists_enabled:
            print("Spotify feature disabled")
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Spotify feature is disabled'})
            }

        # Get Spotify credentials
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

        if not client_id or not client_secret:
            print("Missing Spotify credentials")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Missing Spotify credentials'})
            }

        # Get refresh token
        refresh_token = get_spotify_refresh_token()
        if not refresh_token:
            print("Missing Spotify refresh token")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Missing Spotify refresh token'})
            }

        if refresh_token == 'PLACEHOLDER_UPDATE_AFTER_AUTHORIZATION':
            print("Refresh token not yet configured - run tools/spotify-authorize.py")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Refresh token not yet configured'})
            }

        # Get Top 10 tracks
        print("Fetching Top 10 tracks")
        top10_tracks = get_top10_tracks()

        if not top10_tracks:
            print("No tracks in Top 10")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No tracks to add to playlist'})
            }

        print(f"Top 10 tracks: {json.dumps(top10_tracks, indent=2)}")

        # Initialize Spotify provider with refresh token
        spotify = SpotifyProvider(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token
        )

        # Create playlist
        print("Creating Spotify playlist")
        playlist_id = create_playlist(spotify, top10_tracks)

        if playlist_id:
            playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
            print(f"Playlist created: {playlist_url}")

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Playlist created successfully',
                    'playlist_id': playlist_id,
                    'playlist_url': playlist_url,
                    'tracks_added': len(top10_tracks)
                })
            }
        else:
            print("Failed to create playlist")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to create playlist'})
            }

    except Exception as e:
        print(f"Error in playlist generator: {e}")
        import traceback
        print(traceback.format_exc())

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
