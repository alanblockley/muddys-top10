#!/usr/bin/env python3
"""
Clean existing track names in DynamoDB history

Applies CLEAN_TITLES.MD logic to all existing tracks
Updates 'track' field with cleaned version

Usage:
    # Dry run (report only)
    python3 clean-history.py

    # Actually clean tracks
    python3 clean-history.py --update
"""

import sys
import os
import boto3
import argparse

# Add layers/common to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'layers/common'))

from common import clean_track_title

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


def analyze_tracks(tracks):
    """Check which tracks need cleaning"""
    needs_cleaning = []

    print("🔍 Analyzing tracks for cleaning...\n")

    for track in tracks:
        current_name = track.get('track', '')
        if not current_name:
            continue

        # Apply cleaning logic
        cleaned_name = clean_track_title(current_name)

        # Check if it changed
        if cleaned_name != current_name:
            needs_cleaning.append({
                'pk': track['pk'],
                'sk': track['sk'],
                'timestamp': track['timestamp'],
                'original': current_name,
                'cleaned': cleaned_name
            })

    return needs_cleaning


def report_changes(changes):
    """Print cleaning report"""
    if not changes:
        print("✅ All tracks are already clean! No updates needed.\n")
        return

    print(f"⚠️  Found {len(changes)} tracks that need cleaning:\n")

    # Show first 10 examples
    for idx, change in enumerate(changes[:10], 1):
        print(f"{idx}. Original: {change['original']}")
        print(f"   Cleaned:  {change['cleaned']}")
        print()

    if len(changes) > 10:
        print(f"   ... and {len(changes) - 10} more\n")


def update_tracks(table, changes, dry_run=True):
    """Update track names in DynamoDB"""
    if dry_run:
        print(f"🔍 DRY RUN: Would clean {len(changes)} track names")
        print("   Run with --update flag to actually update\n")
        return

    print(f"🧹 Cleaning {len(changes)} track names...")

    updated = 0
    errors = 0

    for change in changes:
        try:
            # Update the track field
            table.update_item(
                Key={
                    'pk': change['pk'],
                    'sk': change['sk']
                },
                UpdateExpression='SET track = :cleaned',
                ExpressionAttributeValues={
                    ':cleaned': change['cleaned']
                }
            )
            updated += 1

            if updated % 10 == 0:
                print(f"   Updated {updated}/{len(changes)}...")

        except Exception as e:
            print(f"   Error updating {change['sk']}: {e}")
            errors += 1

    print(f"\n✅ Updated {updated} tracks")
    if errors > 0:
        print(f"⚠️  {errors} errors")
    print()


def main():
    parser = argparse.ArgumentParser(description='Clean track names in DynamoDB history')
    parser.add_argument('--update', action='store_true', help='Actually update tracks (default: dry run)')
    args = parser.parse_args()

    print("╔════════════════════════════════════════════════════════════════╗")
    print("║           Muddy's Top 10 - History Cleaner                   ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()

    # Get table
    table_name = get_table_name()
    print(f"📋 Table: {table_name}\n")

    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.Table(table_name)

    # Scan all tracks
    tracks = scan_all_tracks(table)

    # Analyze which need cleaning
    changes = analyze_tracks(tracks)

    # Report
    report_changes(changes)

    # Update if requested
    if changes:
        update_tracks(table, changes, dry_run=not args.update)

    print("═══════════════════════════════════════════════════════════════════")


if __name__ == '__main__':
    main()
