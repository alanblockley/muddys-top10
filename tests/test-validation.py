#!/usr/bin/env python3
"""
Test track validation against MusicBrainz/Spotify APIs
"""
import sys
import os

# Add layers/common to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'layers/common'))

from track_normalizer import parse_track, generate_search_candidates
from music_providers import search_all_providers

def test_track(track_name, spotify_client_id=None, spotify_client_secret=None):
    """Test validation for a specific track"""
    print(f"╔════════════════════════════════════════════════════════════════╗")
    print(f"║ Testing Track Validation")
    print(f"╚════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Input: {track_name}")
    print()

    # Parse the track
    parsed = parse_track(track_name)
    print(f"📝 Parsed:")
    print(f"   Artist: {parsed.artist}")
    print(f"   Title: {parsed.title}")
    print(f"   Context: {parsed.context}")
    print(f"   Confidence: {parsed.parse_confidence}")
    print()

    # Generate search candidates
    candidates = generate_search_candidates(parsed)
    print(f"🔍 Generated {len(candidates)} search candidates:")
    for i, candidate in enumerate(candidates[:5], 1):
        artist = candidate.get('artist', 'None')
        title = candidate['title']
        priority = candidate['priority']
        print(f"   {i}. [{priority}] artist='{artist}', title='{title}'")
    print()

    # Search providers
    print(f"🌐 Searching music providers...")
    if spotify_client_id and spotify_client_secret:
        print(f"   Using: MusicBrainz + Spotify")
    else:
        print(f"   Using: MusicBrainz only (no Spotify credentials)")
    print()

    all_matches = []
    for candidate in candidates[:3]:  # Top 3 candidates
        matches = search_all_providers(
            artist=candidate.get('artist'),
            title=candidate['title'],
            spotify_client_id=spotify_client_id,
            spotify_client_secret=spotify_client_secret
        )
        all_matches.extend(matches)

    if not all_matches:
        print("❌ No matches found")
        return

    # Show top 5 matches
    print(f"📊 Top Matches:")
    for i, match in enumerate(all_matches[:5], 1):
        print(f"\n   Match #{i}:")
        print(f"      Artist: {match.artist}")
        print(f"      Title: {match.title}")
        print(f"      Source: {match.source}")
        print(f"      Confidence: {match.confidence}")
        print(f"      Scores: artist={match.artist_score:.2f}, title={match.title_score:.2f}, total={match.total_score:.2f}")

        if match.release:
            print(f"      Release: {match.release}")

    # Best match
    best = all_matches[0]
    print(f"\n✅ Best Match:")
    print(f"   Canonical: {best.artist} - {best.title}")
    print(f"   Confidence: {best.confidence}")
    print(f"   Total Score: {best.total_score:.2f}")
    print()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Test track validation')
    parser.add_argument('track', nargs='?', help='Track name to test')
    parser.add_argument('--spotify-id', help='Spotify Client ID')
    parser.add_argument('--spotify-secret', help='Spotify Client Secret')
    args = parser.parse_args()

    # Default test track
    track = args.track or "HUNTR/X/EJAE/AUDREY NUNA/REI AMI/KPop Demon Hunters Cast - Golden"

    # Get Spotify credentials from env or args
    spotify_id = args.spotify_id or os.environ.get('SPOTIFY_CLIENT_ID')
    spotify_secret = args.spotify_secret or os.environ.get('SPOTIFY_CLIENT_SECRET')

    test_track(track, spotify_id, spotify_secret)
