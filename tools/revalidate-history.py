#!/usr/bin/env python3
"""
Re-validate existing tracks in DynamoDB history

Applies updated validation logic (including fuzzy matching improvements)
to existing tracks. Useful after improving validation rules.

Usage:
    # Dry run (report only)
    python3 revalidate-history.py

    # Re-validate all unvalidated tracks
    python3 revalidate-history.py --update

    # Re-validate specific pattern (e.g., HUNTRIX)
    python3 revalidate-history.py --pattern "HUNTRIX" --update

    # Re-validate low confidence tracks
    python3 revalidate-history.py --low-confidence --update
"""

import sys
import os
import boto3
import argparse
import time

# Add layers/common to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'layers/common'))

from track_normalizer import parse_track, generate_search_candidates
from music_providers import search_all_providers

# Configuration
STACK_NAME = "muddys-now-playing"


def get_table_name():
    """Get tracks table name from CloudFormation stack"""
    cf = boto3.client('cloudformation', region_name='us-west-2')
    response = cf.describe_stacks(StackName=STACK_NAME)

    outputs = response['Stacks'][0]['Outputs']
    for output in outputs:
        if output['OutputKey'] == 'TracksTableName':
            return output['OutputValue']

    raise Exception("Could not find TracksTableName in stack outputs")


def get_spotify_credentials():
    """Get Spotify credentials from environment"""
    return (
        os.environ.get('SPOTIFY_CLIENT_ID'),
        os.environ.get('SPOTIFY_CLIENT_SECRET')
    )


def scan_tracks(table, pattern=None, low_confidence=False):
    """Scan table for tracks that need re-validation"""
    print("📊 Scanning DynamoDB table...")

    tracks = []
    last_evaluated_key = None

    while True:
        if last_evaluated_key:
            response = table.scan(ExclusiveStartKey=last_evaluated_key)
        else:
            response = table.scan()

        items = response.get('Items', [])

        # Filter based on criteria
        for item in items:
            track_name = item.get('track', '')

            # Skip if no track name
            if not track_name:
                continue

            # Apply filters
            if pattern and pattern.lower() not in track_name.lower():
                continue

            if low_confidence:
                confidence = item.get('validation_confidence', 'unvalidated')
                if confidence not in ['low', 'unvalidated']:
                    continue

            tracks.append(item)

        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break

        print(f"   Scanned {len(tracks)} matching records so far...")

    print(f"✅ Found {len(tracks)} tracks to re-validate\n")
    return tracks


def validate_track(track_name, spotify_client_id=None, spotify_client_secret=None, use_spotify=True):
    """Validate a track using current validation logic"""
    # Parse the track
    parsed = parse_track(track_name)

    # Generate search candidates
    candidates = generate_search_candidates(parsed)

    # Search all providers
    all_matches = []
    for candidate in candidates[:3]:  # Top 3 candidates
        matches = search_all_providers(
            artist=candidate.get('artist'),
            title=candidate['title'],
            spotify_client_id=spotify_client_id if use_spotify else None,
            spotify_client_secret=spotify_client_secret if use_spotify else None
        )
        all_matches.extend(matches)

    if not all_matches:
        return {
            'validated': False,
            'canonical_track': track_name,
            'confidence': 'unvalidated'
        }

    # Get best match
    best_match = all_matches[0]

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
        return {
            'validated': False,
            'canonical_track': track_name,
            'confidence': 'low'
        }


def revalidate_tracks(table, tracks, dry_run=True, use_spotify=True):
    """Re-validate tracks and update DynamoDB"""
    spotify_id, spotify_secret = get_spotify_credentials()

    if use_spotify and spotify_id and spotify_secret:
        print("🎵 Using MusicBrainz + Spotify\n")
    elif not use_spotify:
        print("🎵 Using MusicBrainz only (--no-spotify flag)\n")
        spotify_id = None
        spotify_secret = None
    else:
        print("🎵 Using MusicBrainz only (set SPOTIFY_CLIENT_ID for better results)\n")

    if dry_run:
        print(f"🔍 DRY RUN: Would re-validate {len(tracks)} tracks")
        print("   Run with --update flag to actually update\n")

    updated = 0
    improved = 0
    unchanged = 0
    errors = 0

    for idx, track in enumerate(tracks, 1):
        track_name = track.get('track', '')
        old_canonical = track.get('canonical_track', track_name)
        old_confidence = track.get('validation_confidence', 'unvalidated')

        print(f"   [{idx}/{len(tracks)}] Processing: {track_name[:60]}...")

        try:
            # Validate
            result = validate_track(track_name, spotify_id, spotify_secret, use_spotify=use_spotify)

            # Check if it improved
            new_canonical = result['canonical_track']
            new_confidence = result['confidence']

            if new_canonical != old_canonical or new_confidence != old_confidence:
                improved += 1
                print(f"      ✓ Improved: {old_confidence} → {new_confidence}")
                print(f"        Old: {old_canonical}")
                print(f"        New: {new_canonical}")

                if not dry_run:
                    # Update DynamoDB
                    update_expr = 'SET validation_status = :status, canonical_track = :canonical, validation_confidence = :confidence'
                    expr_values = {
                        ':status': 'validated' if result['validated'] else 'unvalidated',
                        ':canonical': new_canonical,
                        ':confidence': new_confidence
                    }

                    if result.get('artist'):
                        update_expr += ', artist = :artist'
                        expr_values[':artist'] = result['artist']

                    if result.get('title'):
                        update_expr += ', title = :title'
                        expr_values[':title'] = result['title']

                    if result.get('music_db_id'):
                        update_expr += ', music_db_id = :db_id, music_db_source = :db_source'
                        expr_values[':db_id'] = result['music_db_id']
                        expr_values[':db_source'] = result['music_db_source']

                    table.update_item(
                        Key={'pk': track['pk'], 'sk': track['sk']},
                        UpdateExpression=update_expr,
                        ExpressionAttributeValues=expr_values
                    )
                    updated += 1
                    print(f"        → Updated in DynamoDB")
            else:
                unchanged += 1
                print(f"      → No change")

            # Rate limit to avoid hitting API limits
            time.sleep(0.5)

        except Exception as e:
            print(f"      ⚠️  Error: {e}")
            import traceback
            error_detail = traceback.format_exc()
            # Only show first 300 chars to avoid spam
            print(f"      Details: {error_detail[:300]}")
            errors += 1
            time.sleep(1)  # Longer delay after errors

    print()
    print(f"✅ Improved: {improved}")
    print(f"   Unchanged: {unchanged}")
    if not dry_run:
        print(f"   Updated: {updated}")
    if errors > 0:
        print(f"⚠️  Errors: {errors}")
    print()


def main():
    parser = argparse.ArgumentParser(description='Re-validate tracks in DynamoDB history')
    parser.add_argument('--update', action='store_true', help='Actually update tracks (default: dry run)')
    parser.add_argument('--pattern', type=str, help='Only re-validate tracks matching pattern (e.g., HUNTRIX)')
    parser.add_argument('--low-confidence', action='store_true', help='Only re-validate low confidence tracks')
    parser.add_argument('--no-spotify', action='store_true', help='Skip Spotify (use MusicBrainz only, avoids rate limits)')
    args = parser.parse_args()

    print("╔════════════════════════════════════════════════════════════════╗")
    print("║           Muddy's Top 10 - History Re-Validator              ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()

    # Get table
    table_name = get_table_name()
    print(f"📋 Table: {table_name}")

    if args.pattern:
        print(f"🔍 Pattern: {args.pattern}")
    if args.low_confidence:
        print(f"🔍 Filter: low confidence only")
    if args.no_spotify:
        print(f"⚠️  Spotify disabled (avoiding rate limits)")

    print()

    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.Table(table_name)

    # Scan tracks
    tracks = scan_tracks(table, pattern=args.pattern, low_confidence=args.low_confidence)

    if not tracks:
        print("No tracks found matching criteria.\n")
        return

    # Re-validate
    revalidate_tracks(table, tracks, dry_run=not args.update, use_spotify=not args.no_spotify)

    print("═══════════════════════════════════════════════════════════════════")


if __name__ == '__main__':
    main()
