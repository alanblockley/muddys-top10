"""
Track Validator Lambda
Validates and canonicalizes track names using MusicBrainz/Spotify
Triggered by DynamoDB stream on TracksTable
"""
import os
import json
import re
import boto3
from common import get_env
from track_normalizer import parse_track, generate_search_candidates
from music_providers import search_all_providers

dynamodb = boto3.resource('dynamodb')
tracks_table = dynamodb.Table(get_env('TRACKS_TABLE'))
config_table = dynamodb.Table(get_env('CONFIG_TABLE'))


def should_skip_validation(track_name: str) -> tuple[bool, str]:
    """Check if track should skip validation (promotional content)"""
    try:
        # Get filter patterns from config
        response = config_table.get_item(Key={'configKey': 'top10_filters'})
        filter_patterns = response.get('Item', {}).get('value', [])

        if not filter_patterns:
            return False, 'music'

        # Check if track matches any filter pattern
        for pattern in filter_patterns:
            try:
                if re.search(pattern, track_name, re.IGNORECASE):
                    return True, 'promotional'
            except re.error:
                # Invalid regex, try exact match
                if pattern.lower() in track_name.lower():
                    return True, 'promotional'

        return False, 'music'

    except Exception as e:
        print(f"Error checking filters: {e}")
        return False, 'music'


def validate_track(
    track_name: str,
    spotify_client_id: str = None,
    spotify_client_secret: str = None,
    musicbrainz_enabled: bool = True,
    spotify_enabled: bool = True
) -> dict:
    """
    Validate and canonicalize a track name
    Returns validation result with canonical name and metadata
    """
    print(f"Validating track: {track_name}")

    # Parse the track
    parsed = parse_track(track_name)
    print(f"Parsed: artist={parsed.artist}, title={parsed.title}, context={parsed.context}")

    # Generate search candidates
    candidates = generate_search_candidates(parsed)
    print(f"Generated {len(candidates)} search candidates")

    # Search all providers
    all_matches = []
    for candidate in candidates[:3]:  # Limit to top 3 candidates to avoid rate limiting
        matches = search_all_providers(
            artist=candidate.get('artist'),
            title=candidate['title'],
            spotify_client_id=spotify_client_id,
            spotify_client_secret=spotify_client_secret,
            musicbrainz_enabled=musicbrainz_enabled,
            spotify_enabled=spotify_enabled
        )
        all_matches.extend(matches)

        # Circuit breaker: if we have good results from MusicBrainz, don't risk Spotify timeout
        if len(all_matches) >= 5:
            print(f"Got {len(all_matches)} results, skipping additional searches to avoid timeout")
            break

    if not all_matches:
        print("No matches found")
        return {
            'validated': False,
            'canonical_track': track_name,
            'artist': parsed.artist,
            'title': parsed.title,
            'confidence': 'unvalidated',
            'music_db_id': None,
            'music_db_source': None
        }

    # Get best match
    best_match = all_matches[0]
    print(f"Best match: {best_match.artist} - {best_match.title} (score: {best_match.total_score:.2f}, confidence: {best_match.confidence})")

    # Accept if confidence is medium or high, or if score is very high
    if (best_match.confidence in ['medium', 'high'] and best_match.total_score > 0.55) or \
       (best_match.total_score > 0.7):
        canonical_track = f"{best_match.artist} - {best_match.title}"

        return {
            'validated': True,
            'canonical_track': canonical_track,
            'artist': best_match.artist,
            'title': best_match.title,
            'confidence': best_match.confidence,
            'music_db_id': best_match.source_id,
            'music_db_source': best_match.source,
            'artist_score': round(best_match.artist_score, 2),
            'title_score': round(best_match.title_score, 2),
            'total_score': round(best_match.total_score, 2)
        }
    else:
        print(f"Match confidence too low: {best_match.confidence}, score: {best_match.total_score:.2f}")
        return {
            'validated': False,
            'canonical_track': track_name,
            'artist': parsed.artist,
            'title': parsed.title,
            'confidence': 'low',
            'music_db_id': None,
            'music_db_source': None
        }


def get_verification_sources():
    """Get validation source settings from config, with env fallback."""
    env_spotify_validation = os.environ.get(
        'ENABLE_SPOTIFY_VALIDATION',
        os.environ.get('ENABLE_SPOTIFY', 'false')
    ).lower() == 'true'

    defaults = {
        'musicbrainz_enabled': True,
        'spotify_validation_enabled': env_spotify_validation
    }

    try:
        response = config_table.get_item(Key={'configKey': 'verification_sources'})
        config = response.get('Item', {}).get('value')
        if not isinstance(config, dict):
            return defaults

        return {
            'musicbrainz_enabled': config_bool(
                config.get('musicbrainz_enabled'),
                defaults['musicbrainz_enabled']
            ),
            'spotify_validation_enabled': config_bool(
                config.get('spotify_validation_enabled'),
                defaults['spotify_validation_enabled']
            )
        }
    except Exception as e:
        print(f"Error reading verification source config: {e}")
        return defaults


def config_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('1', 'true', 'yes', 'y', 'enabled')


def lambda_handler(event, context):
    """
    Process DynamoDB stream events
    Validate tracks and update with canonical names
    """
    print(f"Received {len(event['Records'])} records")

    verification_sources = get_verification_sources()
    spotify_enabled = verification_sources['spotify_validation_enabled']
    spotify_client_id = os.environ.get('SPOTIFY_CLIENT_ID') if spotify_enabled else None
    spotify_client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET') if spotify_enabled else None

    if not spotify_enabled:
        print("Spotify validation source disabled")
    elif spotify_client_id and spotify_client_secret:
        print("Spotify credentials available")
    else:
        print("No Spotify credentials, using MusicBrainz only")

    processed = 0
    skipped = 0
    validated = 0

    for record in event['Records']:
        try:
            # Only process INSERT events
            if record['eventName'] != 'INSERT':
                continue

            # Get new track data
            new_image = record['dynamodb'].get('NewImage', {})

            # Extract track name
            track_name = new_image.get('track', {}).get('S')
            pk = new_image.get('pk', {}).get('S')
            sk = new_image.get('sk', {}).get('S')

            if not track_name or pk != 'TRACK':
                continue

            print(f"Processing: {track_name}")

            # Check if this is promotional content that should skip validation
            should_skip, track_type = should_skip_validation(track_name)

            if should_skip:
                print(f"Skipping validation: promotional content")
                # Update with promotional status
                tracks_table.update_item(
                    Key={'pk': pk, 'sk': sk},
                    UpdateExpression='SET validation_status = :status, canonical_track = :canonical',
                    ExpressionAttributeValues={
                        ':status': 'promotional',
                        ':canonical': track_name
                    }
                )
                skipped += 1
                continue

            # Validate the track with timeout protection
            try:
                result = validate_track(
                    track_name,
                    spotify_client_id,
                    spotify_client_secret,
                    musicbrainz_enabled=verification_sources['musicbrainz_enabled'],
                    spotify_enabled=spotify_enabled
                )
            except Exception as validation_error:
                print(f"Validation failed for {track_name}: {validation_error}")
                # Create a fallback result
                result = {
                    'validated': False,
                    'canonical_track': track_name,
                    'artist': None,
                    'title': None,
                    'confidence': 'error',
                    'music_db_id': None,
                    'music_db_source': None
                }

            # Update DynamoDB with validation result
            update_expression = 'SET validation_status = :status, canonical_track = :canonical, validation_confidence = :confidence'
            expression_values = {
                ':status': 'validated' if result['validated'] else 'unvalidated',
                ':canonical': result['canonical_track'],
                ':confidence': result['confidence']
            }

            if result.get('artist'):
                update_expression += ', artist = :artist'
                expression_values[':artist'] = result['artist']

            if result.get('title'):
                update_expression += ', title = :title'
                expression_values[':title'] = result['title']

            if result.get('music_db_id'):
                update_expression += ', music_db_id = :db_id, music_db_source = :db_source'
                expression_values[':db_id'] = result['music_db_id']
                expression_values[':db_source'] = result['music_db_source']

            tracks_table.update_item(
                Key={'pk': pk, 'sk': sk},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )

            processed += 1
            if result['validated']:
                validated += 1

            print(f"Updated: {result['canonical_track']} (validated: {result['validated']})")

        except Exception as e:
            print(f"Error processing record: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"Processed: {processed}, Validated: {validated}, Skipped: {skipped}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed,
            'validated': validated,
            'skipped': skipped
        })
    }
