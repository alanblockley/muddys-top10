"""
AgentCore Gateway MCP Target Lambda
Standalone Lambda that exposes song history and top10 chart data directly from DynamoDB.
No Cognito auth required - uses IAM auth via AgentCore Gateway.
"""
import os
import re
import json
from decimal import Decimal
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Key


# --- Utilities (self-contained, no layer dependency) ---

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def get_timestamp():
    return int(datetime.now(timezone.utc).timestamp())


def get_hour_block(timestamp):
    pst = ZoneInfo('America/Los_Angeles')
    dt = datetime.fromtimestamp(timestamp, tz=pst)
    block_hour = (dt.hour // 2) * 2
    block_dt = dt.replace(hour=block_hour, minute=0, second=0, microsecond=0)
    return int(block_dt.timestamp())


def format_timestamp(timestamp):
    pst = ZoneInfo('America/Los_Angeles')
    return datetime.fromtimestamp(timestamp, tz=pst).isoformat()


def format_block_label(timestamp):
    pst = ZoneInfo('America/Los_Angeles')
    dt = datetime.fromtimestamp(timestamp, tz=pst)
    return dt.strftime('%Y-%m-%d %I:%M %p PST')


def get_chart_week_start(timestamp, day_of_week='monday', hour=0):
    pst = ZoneInfo('America/Los_Angeles')
    dt = datetime.fromtimestamp(timestamp, tz=pst)
    day_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    target_weekday = day_map.get(day_of_week.lower(), 0)
    days_back = (dt.weekday() - target_weekday) % 7
    reset_dt = dt - timedelta(days=days_back)
    reset_dt = reset_dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    if reset_dt.timestamp() > timestamp:
        reset_dt = reset_dt - timedelta(days=7)
    return int(reset_dt.timestamp())


def chart_event_timestamp_for_week(week_start_timestamp, day_of_week='monday', hour=0):
    chart_tz = ZoneInfo('America/Los_Angeles')
    week_start = datetime.fromtimestamp(week_start_timestamp, tz=chart_tz)
    day_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    target_weekday = day_map.get(str(day_of_week).lower(), 0)
    days_ahead = (target_weekday - week_start.weekday()) % 7
    event_dt = week_start + timedelta(days=days_ahead)
    event_dt = event_dt.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    if event_dt.timestamp() <= week_start_timestamp:
        event_dt = event_dt + timedelta(days=7)
    return int(event_dt.timestamp())


def get_chart_counting_window(timestamp, config):
    reset_day = str(config.get('day', 'monday')).lower()
    reset_hour = int(config.get('hour', 0))
    campaign_day = str(config.get('campaign_day', reset_day)).lower()
    campaign_hour = int(config.get('campaign_hour', reset_hour))
    freeze_enabled = config.get('freeze_enabled', True)
    if isinstance(freeze_enabled, str):
        freeze_enabled = freeze_enabled.lower() in ('1', 'true', 'yes')
    else:
        freeze_enabled = freeze_enabled is not False

    current_time = int(timestamp)
    week_start = get_chart_week_start(current_time, reset_day, reset_hour)
    week_reset_end = chart_event_timestamp_for_week(week_start, reset_day, reset_hour)
    week_count_end = (
        chart_event_timestamp_for_week(week_start, campaign_day, campaign_hour)
        if freeze_enabled else week_reset_end
    )
    if week_count_end > week_reset_end:
        week_count_end = week_reset_end

    previous_week_start = get_chart_week_start(week_start - 1, reset_day, reset_hour)
    previous_reset_end = chart_event_timestamp_for_week(previous_week_start, reset_day, reset_hour)
    previous_count_end = (
        chart_event_timestamp_for_week(previous_week_start, campaign_day, campaign_hour)
        if freeze_enabled else previous_reset_end
    )
    if previous_count_end > previous_reset_end:
        previous_count_end = previous_reset_end

    return {
        'week_start_timestamp': week_start,
        'week_count_end_timestamp': week_count_end,
        'week_reset_end_timestamp': week_reset_end,
        'previous_week_start_timestamp': previous_week_start,
        'previous_week_count_end_timestamp': previous_count_end,
        'previous_week_reset_end_timestamp': previous_reset_end,
    }


# --- DynamoDB setup ---

dynamodb = boto3.resource('dynamodb')
tracks_table = dynamodb.Table(os.environ['TRACKS_TABLE'])
config_table = dynamodb.Table(os.environ['CONFIG_TABLE'])


# --- Tool implementations ---

def should_filter_track(track_name, filter_patterns):
    if not filter_patterns:
        return False
    for pattern in filter_patterns:
        try:
            if re.search(pattern, track_name, re.IGNORECASE):
                return True
        except re.error:
            if pattern.lower() in track_name.lower():
                return True
    return False


def get_config_value(config_key):
    try:
        response = config_table.get_item(Key={'configKey': config_key})
        return response.get('Item', {}).get('value')
    except Exception as e:
        print(f"Error getting config {config_key}: {e}")
        return None


def get_tracks_between(start_ts, end_ts):
    tracks = []
    query_args = {
        'IndexName': 'timestamp-index',
        'KeyConditionExpression': Key('pk').eq('TRACK') & Key('timestamp').between(start_ts, end_ts)
    }
    while True:
        response = tracks_table.query(**query_args)
        for item in response.get('Items', []):
            track_name = item.get('canonical_track', item['track'])
            tracks.append(track_name)
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        query_args['ExclusiveStartKey'] = last_key
    return tracks


def handle_get_history():
    """Get track history grouped by 2-hour blocks (last 7 days)"""
    current_time = get_timestamp()
    seven_days_ago = current_time - (7 * 86400)

    response = tracks_table.query(
        IndexName='timestamp-index',
        KeyConditionExpression=Key('pk').eq('TRACK') & Key('timestamp').gte(seven_days_ago),
        ScanIndexForward=False
    )
    tracks = response.get('Items', [])

    blocks = defaultdict(list)
    for track in tracks:
        timestamp = int(track['timestamp'])
        block_ts = get_hour_block(timestamp)
        display_track = track.get('canonical_track', track['track'])
        blocks[block_ts].append({
            'timestamp': timestamp,
            'formatted_time': format_timestamp(timestamp),
            'track': display_track,
            'raw_track': track['track'],
            'validation_status': track.get('validation_status', 'unvalidated'),
            'artist': track.get('artist'),
            'title': track.get('title'),
        })

    result = []
    for block_ts in sorted(blocks.keys(), reverse=True):
        result.append({
            'block_timestamp': block_ts,
            'block_label': format_block_label(block_ts),
            'tracks': sorted(blocks[block_ts], key=lambda x: x['timestamp'], reverse=True)
        })

    return {
        'blocks': result,
        'total_tracks': len(tracks)
    }


def handle_list_chart_weeks():
    """List available chart weeks that have track data"""
    config_raw = get_config_value('chart_generation')
    config = normalize_chart_config(config_raw)

    current_time = get_timestamp()
    weeks = []

    # Walk backwards week by week, up to 12 weeks
    ts = current_time
    for _ in range(12):
        week_start = get_chart_week_start(ts, config['day'], config['hour'])
        chart_tz = ZoneInfo('America/Los_Angeles')
        week_id = datetime.fromtimestamp(week_start, tz=chart_tz).strftime('%Y-%m-%d')

        # Check if there's any track data in this week
        week_reset_end = chart_event_timestamp_for_week(week_start, config['day'], config['hour'])
        response = tracks_table.query(
            IndexName='timestamp-index',
            KeyConditionExpression=Key('pk').eq('TRACK') & Key('timestamp').between(week_start, week_reset_end),
            Select='COUNT',
            Limit=1
        )
        if response.get('Count', 0) > 0:
            weeks.append({
                'week_id': week_id,
                'week_start': format_timestamp(week_start),
                'week_end': format_timestamp(week_reset_end),
                'chart_day': config['day'],
                'chart_hour': config['hour']
            })

        # Go to previous week
        ts = week_start - 1

    return {
        'weeks': weeks,
        'count': len(weeks),
        'chart_config': config
    }


def handle_get_chart_week(tool_input):
    """Get Top 10 chart for a specific past week by week_id (YYYY-MM-DD)"""
    week_id = tool_input.get('week_id', '').strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', week_id):
        return {'error': 'week_id must be in YYYY-MM-DD format (e.g., 2026-07-19)'}

    config_raw = get_config_value('chart_generation')
    config = normalize_chart_config(config_raw)
    filter_patterns = get_config_value('top10_filters') or []

    # Parse the week_id into a timestamp
    chart_tz = ZoneInfo('America/Los_Angeles')
    try:
        week_date = datetime.strptime(week_id, '%Y-%m-%d').replace(
            hour=config['hour'], minute=0, second=0, tzinfo=chart_tz
        )
        week_start = int(week_date.timestamp())
    except ValueError:
        return {'error': f'Invalid date: {week_id}'}

    # Calculate week end
    week_reset_end = chart_event_timestamp_for_week(week_start, config['day'], config['hour'])

    # Calculate counting window (respect freeze if configured)
    campaign_day = config.get('campaign_day', config['day'])
    campaign_hour = config.get('campaign_hour', config['hour'])
    freeze_enabled = config.get('freeze_enabled', True)
    if freeze_enabled:
        week_count_end = chart_event_timestamp_for_week(week_start, campaign_day, campaign_hour)
        if week_count_end > week_reset_end:
            week_count_end = week_reset_end
    else:
        week_count_end = week_reset_end

    # Previous week for movement comparison
    previous_week_start = get_chart_week_start(week_start - 1, config['day'], config['hour'])
    previous_reset_end = chart_event_timestamp_for_week(previous_week_start, config['day'], config['hour'])
    if freeze_enabled:
        previous_count_end = chart_event_timestamp_for_week(previous_week_start, campaign_day, campaign_hour)
        if previous_count_end > previous_reset_end:
            previous_count_end = previous_reset_end
    else:
        previous_count_end = previous_reset_end

    # Current week counts
    current_tracks = get_tracks_between(week_start, week_count_end)
    current_tracks = [t for t in current_tracks if not should_filter_track(t, filter_patterns)]
    current_counts = Counter(current_tracks)

    if not current_counts:
        return {
            'error': f'No track data found for week starting {week_id}',
            'week_id': week_id,
            'week_start': format_timestamp(week_start),
            'week_end': format_timestamp(week_reset_end)
        }

    # Previous week counts
    previous_tracks = get_tracks_between(previous_week_start, previous_count_end)
    previous_tracks = [t for t in previous_tracks if not should_filter_track(t, filter_patterns)]
    previous_counts = Counter(previous_tracks)

    previous_ranks = {
        track: rank
        for rank, (track, _) in enumerate(previous_counts.most_common(), 1)
    }

    top10 = []
    for rank, (track, count) in enumerate(current_counts.most_common(10), 1):
        prev_rank = previous_ranks.get(track)
        if prev_rank is None:
            movement = 'new'
        elif prev_rank > rank:
            movement = 'up'
        elif prev_rank < rank:
            movement = 'down'
        else:
            movement = 'same'

        top10.append({
            'rank': rank,
            'track': track,
            'play_count': count,
            'previous_rank': prev_rank,
            'movement': movement,
            'movement_delta': (prev_rank - rank) if prev_rank else None
        })

    return {
        'week_id': week_id,
        'top10': top10,
        'chart_date': format_timestamp(week_start),
        'week_start': format_timestamp(week_start),
        'week_end': format_timestamp(week_reset_end),
        'summary': {
            'total_plays': sum(current_counts.values()),
            'unique_tracks': len(current_counts)
        }
    }


def handle_get_top10():
    """Get current Top 10 chart with movement indicators"""
    config_raw = get_config_value('chart_generation')
    config = normalize_chart_config(config_raw)
    filter_patterns = get_config_value('top10_filters') or []

    current_time = get_timestamp()
    chart_window = get_chart_counting_window(current_time, config)

    chart_timestamp = chart_window['week_start_timestamp']
    current_week_count_end = chart_window['week_count_end_timestamp']
    previous_week_start = chart_window['previous_week_start_timestamp']
    previous_week_count_end = chart_window['previous_week_count_end_timestamp']

    # Current week counts
    current_tracks = get_tracks_between(chart_timestamp, current_week_count_end)
    current_tracks = [t for t in current_tracks if not should_filter_track(t, filter_patterns)]
    current_counts = Counter(current_tracks)

    # Previous week counts
    previous_tracks = get_tracks_between(previous_week_start, previous_week_count_end)
    previous_tracks = [t for t in previous_tracks if not should_filter_track(t, filter_patterns)]
    previous_counts = Counter(previous_tracks)

    previous_ranks = {
        track: rank
        for rank, (track, _) in enumerate(previous_counts.most_common(), 1)
    }

    top10 = []
    for rank, (track, count) in enumerate(current_counts.most_common(10), 1):
        prev_rank = previous_ranks.get(track)
        if prev_rank is None:
            movement = 'new'
        elif prev_rank > rank:
            movement = 'up'
        elif prev_rank < rank:
            movement = 'down'
        else:
            movement = 'same'

        top10.append({
            'rank': rank,
            'track': track,
            'play_count': count,
            'previous_rank': prev_rank,
            'movement': movement,
            'movement_delta': (prev_rank - rank) if prev_rank else None
        })

    return {
        'top10': top10,
        'chart_date': format_timestamp(chart_timestamp),
        'week_start': format_timestamp(chart_timestamp),
        'week_end': format_timestamp(current_week_count_end)
    }


def normalize_chart_config(config):
    config = config if isinstance(config, dict) else {}
    valid_days = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}
    day = str(config.get('day', 'monday')).lower()
    if day not in valid_days:
        day = 'monday'
    hour = config.get('hour', 0)
    try:
        hour = max(0, min(23, int(hour)))
    except (TypeError, ValueError):
        hour = 0

    campaign_day = str(config.get('campaign_day', day)).lower()
    if campaign_day not in valid_days:
        campaign_day = day
    campaign_hour = config.get('campaign_hour', hour)
    try:
        campaign_hour = max(0, min(23, int(campaign_hour)))
    except (TypeError, ValueError):
        campaign_hour = hour

    return {
        'day': day,
        'hour': hour,
        'campaign_day': campaign_day,
        'campaign_hour': campaign_hour,
        'freeze_enabled': config.get('freeze_enabled', True)
    }


# --- Lambda handler ---

def lambda_handler(event, context):
    """
    AgentCore Gateway MCP target handler.
    Expects tool invocation events from the gateway.
    """
    print(f"Event: {json.dumps(event, default=str)}")

    # AgentCore Gateway sends events with different possible shapes.
    # Handle both direct tool call format and API Gateway proxy format.
    tool_name = None
    tool_input = {}

    # Format 1: Direct AgentCore Gateway tool invocation
    if 'toolName' in event:
        tool_name = event['toolName']
        tool_input = event.get('toolInput', {}) or event.get('input', {})
    # Format 2: API Gateway proxy format (path-based routing)
    elif 'path' in event:
        path = event.get('path', '')
        if '/top10' in path:
            tool_name = 'get_top10'
        elif '/history' in path:
            tool_name = 'get_history'
    # Format 3: Body contains tool info
    elif 'body' in event:
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            tool_name = body.get('toolName') or body.get('tool_name')
            tool_input = body.get('toolInput') or body.get('input') or {}
        except (json.JSONDecodeError, TypeError):
            pass

    # Route to handler
    try:
        if tool_name in ('get_top10', 'getTop10', 'top10'):
            result = handle_get_top10()
        elif tool_name in ('get_history', 'getHistory', 'history', 'get_song_history'):
            result = handle_get_history()
        elif tool_name in ('get_chart_week', 'getChartWeek', 'chart_week'):
            result = handle_get_chart_week(tool_input)
        elif tool_name in ('list_chart_weeks', 'listChartWeeks', 'chart_weeks'):
            result = handle_list_chart_weeks()
        else:
            result = {
                'error': f'Unknown tool: {tool_name}',
                'available_tools': ['get_top10', 'get_history', 'get_chart_week', 'list_chart_weeks']
            }
            return {
                'statusCode': 400,
                'body': json.dumps(result, cls=DecimalEncoder)
            }

        return {
            'statusCode': 200,
            'body': json.dumps(result, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error handling tool {tool_name}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
