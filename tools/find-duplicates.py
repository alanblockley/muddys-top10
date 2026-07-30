#!/usr/bin/env python3
"""
Find and optionally remove duplicate tracks in DynamoDB

Duplicates are defined as:
- Same track name (using 'track' field, not canonical_track)
- Logged within 5 minutes of each other (typical song length)

Usage:
    # Dry run (report only)
    python3 find-duplicates.py

    # Actually delete duplicates
    python3 find-duplicates.py --delete

    # Custom time window
    python3 find-duplicates.py --window 300  # 5 minutes in seconds
"""

import boto3
import argparse
from collections import defaultdict
from datetime import datetime

# Configuration
STACK_NAME = "muddys-now-playing"
DUPLICATE_WINDOW = 300  # seconds (5 minutes)


def get_table_name():
    """Get tracks table name from CloudFormation stack"""
    cf = boto3.client('cloudformation', region_name='us-west-2')
    response = cf.describe_stacks(StackName=STACK_NAME)

    outputs = response['Stacks'][0]['Outputs']
    for output in outputs:
        if output['OutputKey'] == 'TracksTableName':
            return output['OutputValue']

    raise Exception("Could not find TracksTableName in stack outputs")


def scan_all_tracks(table):
    """Scan entire DynamoDB table and return all tracks"""
    print("📊 Scanning DynamoDB table...")

    tracks = []
    last_evaluated_key = None

    while True:
        if last_evaluated_key:
            response = table.scan(ExclusiveStartKey=last_evaluated_key)
        else:
            response = table.scan()

        tracks.extend(response.get('Items', []))

        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break

        print(f"   Scanned {len(tracks)} records so far...")

    print(f"✅ Found {len(tracks)} total records\n")
    return tracks


def find_duplicates(tracks, window_seconds=DUPLICATE_WINDOW):
    """Find duplicate tracks within time window"""
    print(f"🔍 Looking for duplicates (within {window_seconds}s window)...\n")

    # Sort by timestamp
    sorted_tracks = sorted(tracks, key=lambda x: int(x['timestamp']))

    duplicates = []
    i = 0

    while i < len(sorted_tracks):
        current = sorted_tracks[i]
        current_track_name = current.get('track', '')
        current_timestamp = int(current['timestamp'])

        # Look ahead for duplicates
        duplicates_group = []
        j = i + 1

        while j < len(sorted_tracks):
            next_track = sorted_tracks[j]
            next_track_name = next_track.get('track', '')
            next_timestamp = int(next_track['timestamp'])

            # Check if same track and within window
            if (next_track_name == current_track_name and
                next_timestamp - current_timestamp <= window_seconds):
                duplicates_group.append(next_track)
                j += 1
            else:
                break

        # If we found duplicates, record them
        if duplicates_group:
            duplicates.append({
                'original': current,
                'duplicates': duplicates_group
            })
            i = j  # Skip past all duplicates
        else:
            i += 1

    return duplicates


def format_timestamp(ts):
    """Format Unix timestamp as readable date"""
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def report_duplicates(duplicates):
    """Print duplicate report"""
    if not duplicates:
        print("✅ No duplicates found!\n")
        return

    total_dupes = sum(len(d['duplicates']) for d in duplicates)
    print(f"⚠️  Found {len(duplicates)} duplicate groups ({total_dupes} duplicate records)\n")

    for idx, group in enumerate(duplicates, 1):
        original = group['original']
        dupes = group['duplicates']

        print(f"Group {idx}:")
        print(f"  Track: {original.get('track', 'Unknown')}")
        print(f"  Original: {format_timestamp(int(original['timestamp']))}")

        for dupe in dupes:
            time_diff = int(dupe['timestamp']) - int(original['timestamp'])
            print(f"    Duplicate: {format_timestamp(int(dupe['timestamp']))} (+{time_diff}s)")

        print()


def delete_duplicates(table, duplicates, dry_run=True):
    """Delete duplicate records from DynamoDB"""
    total_dupes = sum(len(d['duplicates']) for d in duplicates)

    if dry_run:
        print(f"🔍 DRY RUN: Would delete {total_dupes} duplicate records")
        print("   Run with --delete flag to actually delete\n")
        return

    print(f"🗑️  Deleting {total_dupes} duplicate records...")

    deleted = 0
    for group in duplicates:
        for dupe in group['duplicates']:
            try:
                table.delete_item(
                    Key={
                        'pk': dupe['pk'],
                        'sk': dupe['sk']
                    }
                )
                deleted += 1
                if deleted % 10 == 0:
                    print(f"   Deleted {deleted}/{total_dupes}...")
            except Exception as e:
                print(f"   Error deleting {dupe['sk']}: {e}")

    print(f"✅ Deleted {deleted} duplicate records\n")


def main():
    parser = argparse.ArgumentParser(description='Find and remove duplicate tracks in DynamoDB')
    parser.add_argument('--delete', action='store_true', help='Actually delete duplicates (default: dry run)')
    parser.add_argument('--window', type=int, default=DUPLICATE_WINDOW, help='Time window in seconds (default: 300)')
    args = parser.parse_args()

    print("╔════════════════════════════════════════════════════════════════╗")
    print("║           Muddy's Top 10 - Duplicate Finder                  ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()

    # Get table
    table_name = get_table_name()
    print(f"📋 Table: {table_name}\n")

    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.Table(table_name)

    # Scan all tracks
    tracks = scan_all_tracks(table)

    # Find duplicates
    duplicates = find_duplicates(tracks, args.window)

    # Report
    report_duplicates(duplicates)

    # Delete if requested
    if duplicates:
        delete_duplicates(table, duplicates, dry_run=not args.delete)

    print("═══════════════════════════════════════════════════════════════════")


if __name__ == '__main__':
    main()
