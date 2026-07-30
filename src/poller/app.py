"""
Stream Poller Lambda
Polls the Shoutcast stream and logs tracks to DynamoDB
"""
import os
import json
import html
import boto3
from boto3.dynamodb.conditions import Key
import urllib3
from common import get_env, get_timestamp, clean_track_title

# Suppress SSL warnings
urllib3.disable_warnings()

dynamodb = boto3.resource('dynamodb')
tracks_table = dynamodb.Table(get_env('TRACKS_TABLE'))
http = urllib3.PoolManager()


def get_last_track():
    """Get the most recent track from DynamoDB (raw/cleaned version)"""
    try:
        response = tracks_table.query(
            IndexName='timestamp-index',
            KeyConditionExpression=Key('pk').eq('TRACK'),
            ScanIndexForward=False,  # Most recent first
            Limit=1
        )

        items = response.get('Items', [])
        if items:
            # Use raw 'track' field (cleaned but not validated)
            # Do NOT use canonical_track - that's for display only
            return items[0].get('track')
        return None
    except Exception as e:
        print(f"Error getting last track: {e}")
        return None


def parse_7html_format(data):
    """Parse 7.html CSV format"""
    # Remove HTML tags
    data = data.replace('<html><body>', '').replace('</body></html>', '')
    parts = data.split(',')

    if len(parts) >= 7:
        track = ','.join(parts[6:])  # Handle tracks with commas
        return {
            'track': html.unescape(track.strip()),
            'backup_status': False  # 7.html format doesn't have backup status
        }
    return None


def parse_xml_format(data):
    """Parse stats?sid= XML format"""
    import xml.etree.ElementTree as ET

    try:
        # Parse XML
        root = ET.fromstring(data)

        # Get SONGTITLE element
        songtitle = root.find('SONGTITLE')
        if songtitle is None or not songtitle.text:
            return None

        track = html.unescape(songtitle.text.strip())

        # Get BACKUPSTATUS element (0 or 1)
        backup_status = False
        backup_element = root.find('BACKUPSTATUS')
        if backup_element is not None and backup_element.text:
            backup_status = backup_element.text.strip() == '1'

        return {
            'track': track,
            'backup_status': backup_status
        }

    except Exception as e:
        print(f"Error parsing XML: {e}")
        return None


def get_current_track():
    """Fetch the current track from the stream."""
    try:
        stream_url = get_env('STREAM_URL')
        response = http.request('GET', stream_url, timeout=5.0)

        if response.status != 200:
            print(f"Error: HTTP {response.status}")
            return None

        data = response.data.decode('utf-8').strip()

        # Detect format based on URL
        if stream_url.endswith('7.html'):
            print("Using 7.html format parser")
            return parse_7html_format(data)
        elif 'stats?' in stream_url or 'stats&' in stream_url:
            print("Using XML format parser")
            return parse_xml_format(data)
        else:
            # Try to auto-detect based on content
            if data.startswith('<?xml') or data.startswith('<SHOUTCASTSERVER'):
                print("Auto-detected XML format")
                return parse_xml_format(data)
            else:
                print("Auto-detected 7.html format")
                return parse_7html_format(data)

    except Exception as e:
        print(f"Error fetching track: {e}")
        return None


def save_track(track, timestamp, backup_status=False):
    """Save track to DynamoDB"""
    try:
        item = {
            'pk': 'TRACK',
            'sk': f'TS#{timestamp}',
            'timestamp': timestamp,
            'track': track,
            'backup_status': backup_status
            # No TTL - keep forever
        }

        tracks_table.put_item(Item=item)
        backup_indicator = " [BACKUP]" if backup_status else ""
        print(f"Saved: {track}{backup_indicator}")
        return True
    except Exception as e:
        print(f"Error saving track: {e}")
        return False


def lambda_handler(event, context):
    """Lambda handler"""
    print("Polling stream...")

    track_data = get_current_track()

    if not track_data:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to fetch track'})
        }

    # Extract track and backup status
    current_track = track_data['track']
    backup_status = track_data.get('backup_status', False)

    # Clean track title according to CLEAN_TITLES.MD
    cleaned_track = clean_track_title(current_track)

    # Get the last track from DynamoDB (stateless, survives cold starts)
    last_track = get_last_track()

    # Only save if track has changed
    if cleaned_track != last_track:
        timestamp = get_timestamp()
        if save_track(cleaned_track, timestamp, backup_status):
            print(f"Track changed: {last_track} -> {cleaned_track}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Track logged',
                    'track': cleaned_track,
                    'raw_track': current_track,
                    'timestamp': timestamp
                })
            }
    else:
        print(f"Track unchanged: {cleaned_track}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'No change',
            'track': cleaned_track
        })
    }
