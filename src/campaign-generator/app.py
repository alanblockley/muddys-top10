"""
Scheduled campaign generator.

Runs outside Cognito user scope. EventBridge invokes this function with an IAM
service role, and the function creates or regenerates a campaign draft from
persisted Top 10 history.
"""
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config
from boto3.dynamodb.conditions import Key

from campaign_store import update_campaign_progress, valid_week_id
from common import api_response, get_env, get_timestamp, get_chart_counting_window, format_timestamp


agentcore_client = boto3.client(
    'bedrock-agentcore',
    config=Config(connect_timeout=10, read_timeout=300, retries={'max_attempts': 0})
)
dynamodb = boto3.resource('dynamodb')
tracks_table = dynamodb.Table(get_env('TRACKS_TABLE'))
config_table = dynamodb.Table(get_env('CONFIG_TABLE'))
chart_history_table = dynamodb.Table(get_env('CHART_HISTORY_TABLE'))
campaigns_table = dynamodb.Table(get_env('CAMPAIGNS_TABLE'))


def lambda_handler(event, context):
    print(f"Campaign generator event: {json.dumps(event)}")

    try:
        week_id = event.get('week_id')
        if week_id and not valid_week_id(week_id):
            return api_response(400, {'error': 'week_id must be in YYYY-MM-DD format'})

        sections = parse_sections(event.get('sections'))
        requested_by = event.get('requested_by')
        generated_by = event.get('generated_by') or 'scheduled-agent'
        if not week_id:
            progress_week_id = 'latest'
            print_progress(progress_week_id, 'snapshotting_current_chart', 'Snapshotting the current unfinished Top 10 before campaign generation.')
            snapshot = build_top10_snapshot()
            chart_history_table.put_item(Item=snapshot)
            week_id = snapshot['week_id']
            print(f"Saved campaign source snapshot for week: {week_id}")
            print_progress(week_id, 'snapshot_saved', 'Current Top 10 snapshot saved; preparing campaign generation.')
        else:
            print_progress(week_id, 'generator_started', 'Campaign generation started.')

        print_progress(week_id, 'generating_campaign', 'Generating campaign assets.')
        tool_result = invoke_agentcore_campaign_runtime({
            'action': 'create_chart_campaign',
            'week_id': week_id,
            'sections': sections,
            'requested_by': requested_by,
            'generated_by': generated_by
        })
        print(f"AgentCore campaign result summary: {json.dumps(result_summary(tool_result), default=str)}")
        campaign = tool_result.get('campaign')
        if not campaign:
            raise RuntimeError('AgentCore campaign tool did not return a campaign')
        if campaign.get('week_id') != week_id:
            raise RuntimeError(f"AgentCore campaign week mismatch: requested {week_id}, returned {campaign.get('week_id')}")

        print_progress(week_id, 'complete', 'Campaign generated successfully.', status=campaign.get('status', 'draft'))
        return api_response(200, {
            'message': 'Campaign draft generated',
            'week_id': campaign['week_id'],
            'status': campaign['status'],
            'generated_by': campaign['generated_by'],
            'source_snapshot_key': campaign.get('source_snapshot_key')
        })

    except ValueError as e:
        return api_response(400, {'error': str(e)})
    except Exception as e:
        print(f"Error generating campaign draft: {e}")
        if 'week_id' in locals() and week_id:
            print_progress(week_id, 'failed', f'Campaign generation failed: {e}', status='failed', error=e)
        import traceback
        traceback.print_exc()
        return api_response(500, {'error': str(e)})


def print_progress(week_id, stage, message, status='processing', error=None):
    if not week_id or week_id == 'latest':
        print(f"Campaign progress [{week_id}]: {stage} - {message}")
        return
    try:
        update_campaign_progress(
            campaigns_table,
            week_id,
            stage,
            message,
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error=error
        )
        print(f"Campaign progress [{week_id}]: {stage} - {message}")
    except Exception as progress_error:
        print(f"Failed to update campaign progress for {week_id}: {progress_error}")


def invoke_agentcore_campaign_runtime(payload):
    runtime_arn = os.environ.get('AGENTCORE_RUNTIME_ARN')
    if not runtime_arn:
        raise RuntimeError('AGENTCORE_RUNTIME_ARN is not configured')

    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        qualifier=os.environ.get('AGENTCORE_RUNTIME_QUALIFIER', 'DEFAULT'),
        runtimeSessionId=agentcore_runtime_session_id(payload, 'schedule'),
        contentType='application/json',
        accept='application/json',
        payload=json.dumps(payload).encode('utf-8')
    )
    raw_payload = read_agentcore_response(response)
    print(f"AgentCore raw response excerpt: {raw_payload[:4000]}")
    result = parse_agentcore_runtime_result(raw_payload)
    if not result.get('ok', False):
        raise RuntimeError(agentcore_error_message(result))
    return result


def parse_agentcore_runtime_result(raw_payload):
    result = json.loads(raw_payload or '{}')
    if isinstance(result, dict) and 'ok' in result:
        return result

    if isinstance(result, dict) and result.get('status') == 'success':
        for content in result.get('content') or []:
            if not isinstance(content, dict) or not content.get('text'):
                continue
            nested = json.loads(content['text'])
            if isinstance(nested, dict):
                return nested

    return result if isinstance(result, dict) else {}


def agentcore_error_message(result):
    if not isinstance(result, dict):
        return 'AgentCore Runtime campaign generation failed'
    for key in ('error', 'errorMessage', 'message'):
        if result.get(key):
            return str(result[key])
    details = result.get('details') or result.get('tool_error') or result.get('failure')
    if details:
        return f'AgentCore Runtime campaign generation failed: {details}'
    return 'AgentCore Runtime campaign generation failed'


def result_summary(result):
    campaign = result.get('campaign') if isinstance(result, dict) else None
    if not isinstance(campaign, dict):
        return result
    return {
        'ok': result.get('ok'),
        'week_id': campaign.get('week_id'),
        'status': campaign.get('status'),
        'has_radio_reads': bool(campaign.get('radio_reads')),
        'has_social': bool(campaign.get('social')),
        'has_infographic_asset': bool(campaign.get('infographic_asset')),
        'has_infographic_png': bool(campaign.get('infographic_png')),
        'active_revision_id': campaign.get('active_revision_id')
    }


def agentcore_runtime_session_id(payload, source):
    week_id = payload.get('week_id') or 'latest'
    stack_hint = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'muddys-top10')
    safe_stack_hint = re.sub(r'[^A-Za-z0-9_-]', '-', stack_hint)[-24:]
    safe_week_id = re.sub(r'[^A-Za-z0-9_-]', '-', week_id)
    timestamp = re.sub(r'[^0-9]', '', str(datetime.now(timezone.utc).isoformat())[:19])
    return f"muddys-campaign-{source}-{safe_stack_hint}-{safe_week_id}-{timestamp}"


def read_agentcore_response(response):
    stream = response.get('response')
    if hasattr(stream, 'read'):
        return stream.read().decode('utf-8')
    if stream is None:
        return ''
    chunks = []
    for chunk in stream:
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode('utf-8'))
        elif isinstance(chunk, str):
            chunks.append(chunk)
        elif isinstance(chunk, dict) and 'chunk' in chunk:
            payload = chunk['chunk'].get('bytes') or chunk['chunk'].get('payload')
            if isinstance(payload, bytes):
                chunks.append(payload.decode('utf-8'))
            elif isinstance(payload, str):
                chunks.append(payload)
    return ''.join(chunks)


def parse_sections(value):
    if not value:
        return ['radio', 'infographic', 'social']
    if isinstance(value, str):
        value = [value]

    allowed = {'radio', 'infographic', 'social'}
    sections = [section for section in value if section in allowed]
    if not sections:
        raise ValueError('sections must include one of: radio, infographic, social')
    return sections


def build_top10_snapshot():
    config = normalize_chart_config(get_config_value('chart_generation'))
    filter_patterns = get_config_value('top10_filters') or []
    current_time = get_timestamp()
    chart_window = get_chart_counting_window(current_time, config)

    week_start = chart_window['week_start_timestamp']
    week_count_end = chart_window['week_count_end_timestamp']
    week_reset_end = chart_window['week_reset_end_timestamp']
    previous_week_start = chart_window['previous_week_start_timestamp']
    previous_count_end = chart_window['previous_week_count_end_timestamp']
    previous_reset_end = chart_window['previous_week_reset_end_timestamp']

    current_tracks = [
        track for track in get_tracks_between(week_start, week_count_end)
        if not should_filter_track(track, filter_patterns)
    ]
    previous_tracks = [
        track for track in get_tracks_between(previous_week_start, previous_count_end)
        if not should_filter_track(track, filter_patterns)
    ]
    current_counts = Counter(current_tracks)
    previous_counts = Counter(previous_tracks)
    previous_ranks = {
        track: rank
        for rank, (track, _) in enumerate(previous_counts.most_common(), 1)
    }

    top10 = []
    for rank, (track, count) in enumerate(current_counts.most_common(10), 1):
        previous_rank = previous_ranks.get(track)
        if previous_rank is None:
            movement = 'new'
        elif previous_rank > rank:
            movement = 'up'
        elif previous_rank < rank:
            movement = 'down'
        else:
            movement = 'same'

        top10.append({
            'rank': rank,
            'track': track,
            'play_count': count,
            'previous_rank': previous_rank,
            'movement': movement,
            'movement_delta': (previous_rank - rank) if previous_rank else None
        })

    week_id = chart_week_id(week_start)
    return {
        'pk': 'TOP10_HISTORY',
        'sk': f'WEEK#{week_id}',
        'week_id': week_id,
        'snapshot_type': 'weekly_top10',
        'week_start_timestamp': week_start,
        'week_end_timestamp': week_count_end,
        'week_count_end_timestamp': week_count_end,
        'week_reset_end_timestamp': week_reset_end,
        'previous_week_start_timestamp': previous_week_start,
        'previous_week_count_end_timestamp': previous_count_end,
        'previous_week_reset_end_timestamp': previous_reset_end,
        'generated_at_timestamp': current_time,
        'chart_config': config,
        'filter_patterns': filter_patterns,
        'top10': top10,
        'summary': {
            'total_plays': sum(current_counts.values()),
            'unique_tracks': len(current_counts),
            'previous_total_plays': sum(previous_counts.values()),
            'previous_unique_tracks': len(previous_counts)
        },
        'chart_date': format_timestamp(week_start),
        'week_start': format_timestamp(week_start),
        'week_end': format_timestamp(week_count_end),
        'week_count_end': format_timestamp(week_count_end),
        'week_reset_end': format_timestamp(week_reset_end),
        'previous_week_start': format_timestamp(previous_week_start),
        'previous_week_end': format_timestamp(previous_count_end),
        'previous_week_count_end': format_timestamp(previous_count_end),
        'previous_week_reset_end': format_timestamp(previous_reset_end),
        'freeze_window': {
            'enabled': config.get('freeze_enabled', True),
            'start_timestamp': chart_window['freeze_start_timestamp'],
            'end_timestamp': chart_window['freeze_end_timestamp'],
            'start': format_timestamp(chart_window['freeze_start_timestamp']) if chart_window['freeze_start_timestamp'] else None,
            'end': format_timestamp(chart_window['freeze_end_timestamp']) if chart_window['freeze_end_timestamp'] else None,
            'active': chart_window['is_freeze_window']
        }
    }


def get_tracks_between(start_ts, end_ts):
    tracks = []
    query_args = {
        'IndexName': 'timestamp-index',
        'KeyConditionExpression': Key('pk').eq('TRACK') & Key('timestamp').between(start_ts, end_ts)
    }

    while True:
        response = tracks_table.query(**query_args)
        for item in response.get('Items', []):
            tracks.append(item.get('canonical_track', item['track']))

        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        query_args['ExclusiveStartKey'] = last_key

    return tracks


def get_config_value(config_key):
    try:
        response = config_table.get_item(Key={'configKey': config_key})
        return response.get('Item', {}).get('value')
    except Exception as e:
        print(f"Error getting config {config_key}: {e}")
        return None


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


def chart_week_id(timestamp):
    chart_tz = ZoneInfo('America/Los_Angeles')
    return datetime.fromtimestamp(timestamp, tz=chart_tz).strftime('%Y-%m-%d')


def should_filter_track(track_name, filter_patterns):
    for pattern in filter_patterns:
        try:
            if re.search(pattern, track_name, re.IGNORECASE):
                return True
        except re.error:
            if pattern.lower() in track_name.lower():
                return True
    return False
