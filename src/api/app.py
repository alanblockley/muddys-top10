"""
API Lambda
Handles API Gateway requests for history, top10, and config
"""
import os
import json
import re
import secrets
import hashlib
import base64
import binascii
from itertools import chain
from collections import defaultdict, Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode, parse_qs
import boto3
from boto3.dynamodb.conditions import Key
from common import (
    get_env, api_response, get_timestamp, get_week_start, get_chart_week_start,
    get_chart_counting_window, get_hour_block, format_timestamp, format_block_label
)
from campaign_generation import (
    BedrockCampaignModel,
    generate_infographic_asset,
    generate_infographic_content,
    normalize_campaign_branding,
    utc_now_iso,
    venue_config_with_branding,
)
from campaign_store import (
    delete_campaign,
    approve_campaign_revision,
    get_campaign as load_campaign,
    get_campaign_revision as load_campaign_revision,
    delete_campaign_records,
    list_all_campaign_feedback,
    list_campaign_feedback as load_campaign_feedback,
    list_campaigns as load_campaigns,
    list_campaign_revisions as load_campaign_revisions,
    put_campaign_feedback,
    put_campaign_progress,
    summarize_campaign_feedback,
    update_campaign_content, update_campaign_status, valid_week_id as valid_campaign_week_id
)
from infographic_templates import normalize_template_config, resolve_template, template_public_options
from prompt_management import normalize_prompt_config
from agent_memory import remember_feedback

dynamodb = boto3.resource('dynamodb')
tracks_table = dynamodb.Table(get_env('TRACKS_TABLE'))
config_table = dynamodb.Table(get_env('CONFIG_TABLE'))
chart_history_table = dynamodb.Table(get_env('CHART_HISTORY_TABLE'))
campaigns_table = dynamodb.Table(get_env('CAMPAIGNS_TABLE'))
secrets_client = boto3.client('secretsmanager')
lambda_client = boto3.client('lambda')
agentcore_client = boto3.client('bedrock-agentcore')
s3_client = boto3.client('s3')
logs_client = boto3.client('logs')

# Store PKCE verifiers temporarily (in production, use DynamoDB with TTL)
# For now, using Lambda environment (resets on cold start, but acceptable for OAuth flow)
oauth_state_store = {}


def should_filter_track(track_name, filter_patterns):
    """Check if track should be filtered from Top 10"""
    if not filter_patterns:
        return False

    for pattern in filter_patterns:
        try:
            if re.search(pattern, track_name, re.IGNORECASE):
                return True
        except re.error:
            # Invalid regex, try exact match
            if pattern.lower() in track_name.lower():
                return True

    return False


def get_history(event):
    """Get track history grouped by 2-hour blocks"""
    try:
        # Get all tracks from the last 7 days
        current_time = get_timestamp()
        seven_days_ago = current_time - (7 * 86400)

        response = tracks_table.query(
            IndexName='timestamp-index',
            KeyConditionExpression=Key('pk').eq('TRACK') & Key('timestamp').gte(seven_days_ago),
            ScanIndexForward=False  # Most recent first
        )

        tracks = response.get('Items', [])

        # Group by 2-hour blocks
        blocks = defaultdict(list)
        for track in tracks:
            timestamp = int(track['timestamp'])
            block_ts = get_hour_block(timestamp)
            # Use canonical_track if available, otherwise use raw track
            display_track = track.get('canonical_track', track['track'])
            blocks[block_ts].append({
                'timestamp': timestamp,
                'formatted_time': format_timestamp(timestamp),
                'track': display_track,
                'raw_track': track['track'],
                'validation_status': track.get('validation_status', 'unvalidated'),
                'artist': track.get('artist'),
                'title': track.get('title'),
                'backup_status': track.get('backup_status', False)
            })

        # Convert to sorted list
        result = []
        for block_ts in sorted(blocks.keys(), reverse=True):
            result.append({
                'block_timestamp': block_ts,
                'block_label': format_block_label(block_ts),
                'tracks': sorted(blocks[block_ts], key=lambda x: x['timestamp'], reverse=True)
            })

        return api_response(200, {
            'blocks': result,
            'total_tracks': len(tracks)
        })

    except Exception as e:
        print(f"Error getting history: {e}")
        return api_response(500, {'error': str(e)})


def get_top10(event):
    """Get Top 10 tracks with week-over-week comparison"""
    try:
        snapshot = build_top10_snapshot()
        save_top10_snapshot(snapshot)
        return api_response(200, top10_response_from_snapshot(snapshot))

    except Exception as e:
        print(f"Error getting top10: {e}")
        return api_response(500, {'error': str(e)})


def get_top10_history(event):
    """List persisted weekly Top 10 snapshots for AI-friendly history analysis"""
    try:
        query_params = event.get('queryStringParameters') or {}
        limit = parse_int_param(query_params.get('limit'), 12, 1, 104)
        include_detail = parse_bool_param(query_params.get('detail'), False)
        include_all = parse_bool_param(query_params.get('all'), False)
        from_week = query_params.get('from')
        to_week = query_params.get('to')
        next_token = query_params.get('next_token')

        if from_week and not valid_week_id(from_week):
            return api_response(400, {'error': 'from must be in YYYY-MM-DD format'})
        if to_week and not valid_week_id(to_week):
            return api_response(400, {'error': 'to must be in YYYY-MM-DD format'})
        if from_week and to_week and from_week > to_week:
            return api_response(400, {'error': 'from must be before or equal to to'})

        query_args = {
            'KeyConditionExpression': Key('pk').eq('TOP10_HISTORY'),
            'ScanIndexForward': False
        }

        if from_week or to_week:
            start_key = f'WEEK#{from_week or "0000-01-01"}'
            end_key = f'WEEK#{to_week or "9999-12-31"}'
            query_args['KeyConditionExpression'] = (
                Key('pk').eq('TOP10_HISTORY') & Key('sk').between(start_key, end_key)
            )

        if not include_all:
            query_args['Limit'] = limit

        if next_token:
            try:
                query_args['ExclusiveStartKey'] = decode_page_token(next_token)
            except (ValueError, TypeError, json.JSONDecodeError):
                return api_response(400, {'error': 'Invalid next_token'})

        items = []
        while True:
            response = chart_history_table.query(**query_args)
            items.extend(response.get('Items', []))

            last_key = response.get('LastEvaluatedKey')
            if not include_all or not last_key:
                break

            query_args['ExclusiveStartKey'] = last_key

        next_page_token = None
        if not include_all and response.get('LastEvaluatedKey'):
            next_page_token = encode_page_token(response['LastEvaluatedKey'])

        weeks = [
            public_snapshot(item) if include_detail else history_index_item(item)
            for item in items
        ]

        return api_response(200, {
            'weeks': weeks,
            'count': len(weeks),
            'detail': include_detail,
            'from': from_week,
            'to': to_week,
            'limit': None if include_all else limit,
            'next_token': next_page_token
        })

    except Exception as e:
        print(f"Error getting top10 history: {e}")
        return api_response(500, {'error': str(e)})


def get_top10_history_week(event):
    """Get one persisted weekly Top 10 snapshot by YYYY-MM-DD week id"""
    try:
        week_id = get_week_id_from_event(event)
        if not week_id:
            return api_response(400, {'error': 'Week must be in YYYY-MM-DD format'})

        response = chart_history_table.get_item(
            Key={
                'pk': 'TOP10_HISTORY',
                'sk': f'WEEK#{week_id}'
            }
        )
        snapshot = response.get('Item')
        if not snapshot:
            return api_response(404, {'error': 'Top 10 history week not found', 'week_id': week_id})

        return api_response(200, {
            'snapshot': public_snapshot(snapshot)
        })

    except Exception as e:
        print(f"Error getting top10 history week: {e}")
        return api_response(500, {'error': str(e)})


def build_top10_snapshot():
    """Build the current chart snapshot and week-over-week movement data"""
    config = normalize_chart_config(get_config_value('chart_generation'))
    chart_hour = config['hour']
    chart_day = config['day']

    filter_config = get_config_value('top10_filters')
    filter_patterns = filter_config if filter_config else []

    current_time = get_timestamp()
    chart_window = get_chart_counting_window(current_time, config)

    chart_timestamp = chart_window['week_start_timestamp']
    current_week_count_end = chart_window['week_count_end_timestamp']
    current_week_reset_end = chart_window['week_reset_end_timestamp']
    previous_week_start = chart_window['previous_week_start_timestamp']
    previous_week_count_end = chart_window['previous_week_count_end_timestamp']
    previous_week_reset_end = chart_window['previous_week_reset_end_timestamp']

    current_tracks = get_tracks_between(chart_timestamp, current_week_count_end)
    current_tracks = [t for t in current_tracks if not should_filter_track(t, filter_patterns)]
    current_counts = Counter(current_tracks)

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

    week_id = chart_week_id(chart_timestamp)
    return {
        'pk': 'TOP10_HISTORY',
        'sk': f'WEEK#{week_id}',
        'week_id': week_id,
        'snapshot_type': 'weekly_top10',
        'week_start_timestamp': chart_timestamp,
        'week_end_timestamp': current_week_count_end,
        'week_count_end_timestamp': current_week_count_end,
        'week_reset_end_timestamp': current_week_reset_end,
        'previous_week_start_timestamp': previous_week_start,
        'previous_week_count_end_timestamp': previous_week_count_end,
        'previous_week_reset_end_timestamp': previous_week_reset_end,
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
        'chart_date': format_timestamp(chart_timestamp),
        'week_start': format_timestamp(chart_timestamp),
        'week_end': format_timestamp(current_week_count_end),
        'week_count_end': format_timestamp(current_week_count_end),
        'week_reset_end': format_timestamp(current_week_reset_end),
        'previous_week_start': format_timestamp(previous_week_start),
        'previous_week_end': format_timestamp(previous_week_count_end),
        'previous_week_count_end': format_timestamp(previous_week_count_end),
        'previous_week_reset_end': format_timestamp(previous_week_reset_end),
        'freeze_window': {
            'enabled': config.get('freeze_enabled', True),
            'start_timestamp': chart_window['freeze_start_timestamp'],
            'end_timestamp': chart_window['freeze_end_timestamp'],
            'start': format_timestamp(chart_window['freeze_start_timestamp']) if chart_window['freeze_start_timestamp'] else None,
            'end': format_timestamp(chart_window['freeze_end_timestamp']) if chart_window['freeze_end_timestamp'] else None,
            'active': chart_window['is_freeze_window']
        }
    }


def save_top10_snapshot(snapshot):
    """Persist one item per chart week, replacing the snapshot as the week evolves"""
    chart_history_table.put_item(Item=snapshot)


def top10_response_from_snapshot(snapshot):
    return {
        'top10': snapshot['top10'],
        'chart_date': snapshot['chart_date'],
        'week_start': snapshot['week_start'],
        'week_end': snapshot['week_end'],
        'week_count_end': snapshot.get('week_count_end'),
        'week_reset_end': snapshot.get('week_reset_end'),
        'freeze_window': snapshot.get('freeze_window')
    }


def public_snapshot(snapshot):
    return {
        'snapshot_key': snapshot.get('sk'),
        'week_id': snapshot.get('week_id') or snapshot_key_to_week_id(snapshot.get('sk')),
        'snapshot_type': snapshot.get('snapshot_type', 'weekly_top10'),
        'week_start_timestamp': snapshot.get('week_start_timestamp'),
        'week_end_timestamp': snapshot.get('week_end_timestamp'),
        'week_count_end_timestamp': snapshot.get('week_count_end_timestamp'),
        'week_reset_end_timestamp': snapshot.get('week_reset_end_timestamp'),
        'previous_week_start_timestamp': snapshot.get('previous_week_start_timestamp'),
        'previous_week_count_end_timestamp': snapshot.get('previous_week_count_end_timestamp'),
        'previous_week_reset_end_timestamp': snapshot.get('previous_week_reset_end_timestamp'),
        'generated_at_timestamp': snapshot.get('generated_at_timestamp'),
        'chart_config': snapshot.get('chart_config', {}),
        'filter_patterns': snapshot.get('filter_patterns', []),
        'top10': snapshot.get('top10', []),
        'summary': snapshot.get('summary', {}),
        'chart_date': snapshot.get('chart_date'),
        'week_start': snapshot.get('week_start'),
        'week_end': snapshot.get('week_end'),
        'week_count_end': snapshot.get('week_count_end'),
        'week_reset_end': snapshot.get('week_reset_end'),
        'previous_week_start': snapshot.get('previous_week_start'),
        'previous_week_end': snapshot.get('previous_week_end'),
        'previous_week_count_end': snapshot.get('previous_week_count_end'),
        'previous_week_reset_end': snapshot.get('previous_week_reset_end'),
        'freeze_window': snapshot.get('freeze_window')
    }


def history_index_item(snapshot):
    top10 = snapshot.get('top10', [])
    summary = snapshot.get('summary', {})
    week_id = snapshot.get('week_id') or snapshot_key_to_week_id(snapshot.get('sk'))

    return {
        'week_id': week_id,
        'snapshot_key': snapshot.get('sk'),
        'week_start': snapshot.get('week_start'),
        'week_end': snapshot.get('week_end'),
        'generated_at_timestamp': snapshot.get('generated_at_timestamp'),
        'top10_count': len(top10),
        'total_plays': summary.get('total_plays'),
        'unique_tracks': summary.get('unique_tracks'),
        'href': f'/api/top10/history/{week_id}' if week_id else None
    }


def get_week_id_from_event(event):
    path_params = event.get('pathParameters') or {}
    value = path_params.get('week_id') or path_params.get('week')
    if not value:
        path = event.get('path', '')
        prefix = '/api/top10/history/'
        if path.startswith(prefix):
            value = path[len(prefix):].strip('/')

    if not valid_week_id(value):
        return None
    return value


def valid_week_id(value):
    return bool(value and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value))


def chart_week_id(timestamp):
    chart_tz = ZoneInfo('America/Los_Angeles')
    return datetime.fromtimestamp(timestamp, tz=chart_tz).strftime('%Y-%m-%d')


def snapshot_key_to_week_id(snapshot_key):
    if isinstance(snapshot_key, str) and snapshot_key.startswith('WEEK#'):
        return snapshot_key[5:]
    return None


def parse_int_param(value, default, minimum, maximum):
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def parse_bool_param(value, default=False):
    if value is None:
        return default
    return str(value).lower() in ('1', 'true', 'yes', 'y')


def encode_page_token(last_evaluated_key):
    raw = json.dumps(last_evaluated_key)
    return base64.urlsafe_b64encode(raw.encode('utf-8')).decode('utf-8').rstrip('=')


def decode_page_token(token):
    padding = '=' * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + padding).encode('utf-8'))
    return json.loads(raw.decode('utf-8'))


def get_tracks_between(start_ts, end_ts):
    """Get all track names between two timestamps"""
    tracks = []
    query_args = {
        'IndexName': 'timestamp-index',
        'KeyConditionExpression': Key('pk').eq('TRACK') & Key('timestamp').between(start_ts, end_ts)
    }

    while True:
        response = tracks_table.query(**query_args)
        for item in response.get('Items', []):
            # Use canonical_track if available, otherwise use raw track
            track_name = item.get('canonical_track', item['track'])
            tracks.append(track_name)

        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        query_args['ExclusiveStartKey'] = last_key

    return tracks


def get_config_value(config_key):
    """Get a config value from DynamoDB"""
    try:
        response = config_table.get_item(Key={'configKey': config_key})
        return response.get('Item', {}).get('value')
    except Exception as e:
        print(f"Error getting config: {e}")
        return None


def get_config(event):
    """Get configuration"""
    try:
        chart_config = normalize_chart_config(get_config_value('chart_generation'))
        filter_config = get_config_value('top10_filters') or []
        playlist_config = get_config_value('playlist_generation') or {'hour': 2, 'day': 'saturday'}
        verification_sources = normalize_verification_sources(get_config_value('verification_sources'))
        campaign_branding = normalize_campaign_branding(get_config_value('campaign_branding'))
        campaign_branding = enrich_campaign_logo_url(campaign_branding)
        infographic_template = normalize_template_config(get_config_value('campaign_infographic_template'))
        infographic_template = enrich_infographic_template_reference_url(infographic_template)
        campaign_prompts = normalize_prompt_config(get_config_value('campaign_prompts'))

        return api_response(200, {
            'chart_generation': chart_config,
            'top10_filters': filter_config,
            'playlist_generation': playlist_config,
            'verification_sources': verification_sources,
            'campaign_branding': campaign_branding,
            'campaign_prompts': campaign_prompts,
            'campaign_infographic_template': infographic_template,
            'campaign_infographic_template_options': template_public_options()
        })

    except Exception as e:
        print(f"Error getting config: {e}")
        return api_response(500, {'error': str(e)})


def enrich_campaign_logo_url(campaign_branding):
    key = campaign_branding.get('logo_s3_key')
    bucket = os.environ.get('CAMPAIGN_ASSETS_BUCKET')
    if not key or not bucket:
        return campaign_branding
    try:
        campaign_branding['logo_url'] = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key
            },
            ExpiresIn=3600
        )
    except Exception as e:
        print(f"Error generating campaign logo URL: {e}")
    return campaign_branding


def enrich_infographic_template_reference_url(infographic_template):
    key = infographic_template.get('reference_png_key')
    bucket = os.environ.get('CAMPAIGN_ASSETS_BUCKET')
    if not key or not bucket:
        return infographic_template
    try:
        infographic_template['reference_png_url'] = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentType': 'image/png'
            },
            ExpiresIn=3600
        )
    except Exception as e:
        print(f"Error generating infographic template reference URL: {e}")
    return infographic_template


def put_config(event):
    """Update configuration"""
    try:
        body = json.loads(event.get('body', '{}'))

        if 'chart_generation' in body:
            config_table.put_item(Item={
                'configKey': 'chart_generation',
                'value': normalize_chart_config(body['chart_generation'])
            })

        if 'top10_filters' in body:
            config_table.put_item(Item={
                'configKey': 'top10_filters',
                'value': body['top10_filters']
            })

        if 'playlist_generation' in body:
            config_table.put_item(Item={
                'configKey': 'playlist_generation',
                'value': body['playlist_generation']
            })

        if 'verification_sources' in body:
            config_table.put_item(Item={
                'configKey': 'verification_sources',
                'value': normalize_verification_sources(body['verification_sources'])
            })

        if 'campaign_branding' in body:
            existing_branding = normalize_campaign_branding(get_config_value('campaign_branding'))
            incoming_branding = body['campaign_branding'] if isinstance(body['campaign_branding'], dict) else {}
            for key in ('logo_s3_key', 'logo_content_type', 'logo_filename'):
                if key not in incoming_branding and existing_branding.get(key):
                    incoming_branding[key] = existing_branding[key]
            config_table.put_item(Item={
                'configKey': 'campaign_branding',
                'value': normalize_campaign_branding(incoming_branding)
            })

        if 'campaign_infographic_template' in body:
            existing_template = normalize_template_config(get_config_value('campaign_infographic_template'))
            incoming_template = body['campaign_infographic_template'] if isinstance(body['campaign_infographic_template'], dict) else {}
            for key in ('reference_png_key', 'reference_png_generated_at'):
                if key not in incoming_template and existing_template.get(key):
                    incoming_template[key] = existing_template[key]
            config_table.put_item(Item={
                'configKey': 'campaign_infographic_template',
                'value': normalize_template_config(incoming_template)
            })

        if 'campaign_prompts' in body:
            config_table.put_item(Item={
                'configKey': 'campaign_prompts',
                'value': normalize_prompt_config(body['campaign_prompts'])
            })

        return api_response(200, {'message': 'Config updated'})

    except Exception as e:
        print(f"Error updating config: {e}")
        return api_response(500, {'error': str(e)})


def put_campaign_logo(event):
    try:
        body = parse_json_body(event)
        filename = str(body.get('filename') or 'campaign-logo.png')
        content_type = str(body.get('content_type') or '').lower().strip()
        data = str(body.get('data') or '')
        if ',' in data and data.startswith('data:'):
            header, data = data.split(',', 1)
            if not content_type and ';' in header:
                content_type = header[5:].split(';', 1)[0].lower()

        allowed_types = {
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/webp': 'webp'
        }
        if content_type not in allowed_types:
            return api_response(400, {'error': 'Logo must be PNG, JPEG, or WebP'})

        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            return api_response(400, {'error': 'Logo data must be valid base64'})

        max_bytes = 2 * 1024 * 1024
        if not raw or len(raw) > max_bytes:
            return api_response(400, {'error': 'Resized logo upload must be between 1 byte and 2 MB'})

        bucket = os.environ.get('CAMPAIGN_ASSETS_BUCKET')
        if not bucket:
            raise RuntimeError('CAMPAIGN_ASSETS_BUCKET is not configured')

        safe_name = re.sub(r'[^A-Za-z0-9_.-]', '-', filename).strip('-') or 'campaign-logo'
        key = f'branding/logo-{utc_now_iso().replace(":", "-")}-{safe_name}'
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=raw,
            ContentType=content_type,
            CacheControl='private, max-age=31536000',
            Metadata={
                'uploaded_by': request_actor(event) or '',
                'source_filename': safe_name,
                'original_filename': str(body.get('original_filename') or ''),
                'original_size_bytes': str(body.get('original_size_bytes') or ''),
                'resized_width': str(body.get('resized_width') or ''),
                'resized_height': str(body.get('resized_height') or '')
            }
        )

        current = normalize_campaign_branding(get_config_value('campaign_branding'))
        current.update({
            'logo_variant': 'uploaded',
            'logo_s3_key': key,
            'logo_content_type': content_type,
            'logo_filename': safe_name
        })
        saved = normalize_campaign_branding(current)
        saved['logo_s3_key'] = key
        saved['logo_content_type'] = content_type
        saved['logo_filename'] = safe_name
        config_table.put_item(Item={
            'configKey': 'campaign_branding',
            'value': saved
        })

        return api_response(200, {
            'campaign_branding': saved,
            'logo': {
                'bucket': bucket,
                'key': key,
                'content_type': content_type,
                'filename': safe_name,
                'size_bytes': len(raw)
            }
        })
    except ValueError as e:
        return api_response(400, {'error': str(e)})
    except Exception as e:
        print(f"Error uploading campaign logo: {e}")
        return api_response(500, {'error': str(e)})


def post_infographic_template_reference(event):
    try:
        bucket = os.environ.get('CAMPAIGN_ASSETS_BUCKET')
        function_name = os.environ.get('INFOGRAPHIC_RENDERER_FUNCTION_NAME')
        if not bucket:
            raise RuntimeError('CAMPAIGN_ASSETS_BUCKET is not configured')
        if not function_name:
            raise RuntimeError('INFOGRAPHIC_RENDERER_FUNCTION_NAME is not configured')

        branding = normalize_campaign_branding(get_config_value('campaign_branding'))
        template_config = normalize_template_config(get_config_value('campaign_infographic_template'))
        template = resolve_template(template_config, s3_client=s3_client, bucket=bucket)
        chart_brief = template_reference_chart_brief()
        venue_config = venue_config_with_branding(branding)
        infographic = template_reference_infographic_content(chart_brief, venue_config)
        asset = generate_infographic_asset(chart_brief, infographic, venue_config, template)
        asset['metadata']['asset_role'] = 'template_reference'
        asset['metadata']['reference_intent'] = 'blank_structure_with_placeholders'

        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'week_id': 'template-reference',
                'infographic_asset': asset,
                'output_prefix': f"templates/{template_config['template_id']}/v{template_config['version']}",
                'filename_prefix': 'reference'
            }).encode('utf-8')
        )
        raw_payload = response.get('Payload').read().decode('utf-8')
        result = json.loads(raw_payload or '{}')
        if response.get('FunctionError'):
            raise RuntimeError(result.get('errorMessage') or raw_payload or 'Infographic renderer failed')
        if not result.get('ok') or not result.get('infographic_png'):
            raise RuntimeError(result.get('error') or 'Infographic renderer did not return reference PNG metadata')

        rendered = result['infographic_png']
        updated_template = {
            **template_config,
            'reference_png_key': rendered['key'],
            'reference_png_generated_at': rendered.get('generated_at') or utc_now_iso()
        }
        updated_template = normalize_template_config(updated_template)
        config_table.put_item(Item={
            'configKey': 'campaign_infographic_template',
            'value': updated_template
        })

        return api_response(200, {
            'campaign_infographic_template': enrich_infographic_template_reference_url(updated_template),
            'reference_png': rendered
        })
    except Exception as e:
        print(f"Error generating infographic template reference: {e}")
        return api_response(500, {'error': str(e)})


def template_reference_chart_brief():
    tracks = [
        template_reference_track(1, 'Featured Artist', 'Featured Track Title', 34, 'up', 2, 3, 5),
        template_reference_track(2, 'Artist Name', 'Track Title', 29, 'same', 2, 2, 4),
        template_reference_track(3, 'Artist Name', 'Track Title', 25, 'down', -1, 2, 3),
        template_reference_track(4, 'Artist Name', 'Track Title', 21, 'up', 6, 10, 2),
        template_reference_track(5, 'New Entry Artist', 'New Entry Title', 18, 'new', None, None, 1),
        template_reference_track(6, 'Artist Name', 'Track Title', 15, 'up', 12, 18, 2),
        template_reference_track(7, 'Artist Name', 'Track Title', 14, 'down', -3, 4, 6),
        template_reference_track(8, 'New Entry Artist', 'Track Title', 12, 'new', None, None, 1),
        template_reference_track(9, 'Artist Name', 'Track Title', 11, 'same', 9, 9, 3),
        template_reference_track(10, 'Big Climber Artist', 'Big Climber Title', 10, 'up', 24, 34, 2)
    ]
    return {
        'week_id': 'template-reference',
        'source_snapshot_key': 'TEMPLATE#REFERENCE',
        'tracks': tracks,
        'summary': {
            'total_plays': 'Total Plays',
            'unique_tracks': 'Unique Tracks',
            'history_weeks_available': 'History Weeks'
        },
        'notables': {
            'number_one': tracks[0],
            'biggest_climbers': [tracks[9], tracks[5], tracks[3]],
            'new_entries': [tracks[4], tracks[7]],
            'returning_tracks': []
        }
    }


def template_reference_track(rank, artist, title, play_count, movement, movement_delta, previous_rank, weeks_on_chart):
    return {
        'rank': rank,
        'artist': artist,
        'title': title,
        'track': f'{artist} - {title}',
        'play_count': play_count,
        'previous_rank': previous_rank,
        'movement': movement,
        'movement_delta': movement_delta,
        'weeks_on_chart': weeks_on_chart
    }


def template_reference_infographic_content(chart_brief, venue_config):
    branding = ((venue_config or {}).get('venue') or {}).get('branding', {})
    return {
        'headline': branding.get('chart_title', "Muddy's Top 10"),
        'subhead': 'Weekly chart layout reference',
        'chart_story': 'Use this area for the week-specific chart story, movement narrative, and presenter-friendly highlights.',
        'movement_summary': 'Movement summary placeholder: climbers, fallers, non-movers, new entries, and returning tracks.',
        'statistics': [
            {'label': 'Total Plays', 'value': '###'},
            {'label': 'Unique Tracks', 'value': '###'},
            {'label': 'New Entries', 'value': '##'},
            {'label': 'Biggest Climber', 'value': '+##'}
        ],
        'track_cards': [
            {
                'rank': track['rank'],
                'display_text': track['track'],
                'movement_badge': 'Movement',
                'supporting_line': 'Plays | chart note'
            }
            for track in chart_brief.get('tracks', [])
        ],
        'promotional_footer': branding.get('tagline', 'Your requests. Your music. Your chart.'),
        'self_review': {
            'facts_verified': True,
            'ready_for_publication': True,
            'missing_inputs': []
        }
    }


def list_infographic_templates(event):
    """List uploaded infographic templates (HTML and PNG files)."""
    try:
        templates = get_config_value('infographic_template_uploads') or []
        bucket = os.environ.get('CAMPAIGN_ASSETS_BUCKET')
        for tpl in templates:
            if tpl.get('s3_key') and bucket:
                try:
                    tpl['url'] = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket, 'Key': tpl['s3_key']},
                        ExpiresIn=3600
                    )
                except Exception:
                    tpl['url'] = None
        return api_response(200, {'templates': templates})
    except Exception as e:
        print(f"Error listing infographic templates: {e}")
        return api_response(500, {'error': str(e)})


def upload_infographic_template(event):
    """Upload a named infographic template (HTML or PNG)."""
    try:
        body = parse_json_body(event)
        name = str(body.get('name') or '').strip()
        if not name or len(name) > 100:
            return api_response(400, {'error': 'Template name is required (max 100 characters)'})

        filename = str(body.get('filename') or '').strip()
        content_type = str(body.get('content_type') or '').lower().strip()
        data = str(body.get('data') or '')

        # Handle data URI prefix
        if ',' in data and data.startswith('data:'):
            header, data = data.split(',', 1)
            if not content_type and ';' in header:
                content_type = header[5:].split(';', 1)[0].lower()

        allowed_types = {
            'image/png': 'png',
            'text/html': 'html',
            'application/html': 'html',
        }
        if content_type not in allowed_types:
            return api_response(400, {'error': 'Template must be PNG or HTML file'})

        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            return api_response(400, {'error': 'File data must be valid base64'})

        max_bytes = 5 * 1024 * 1024
        if not raw or len(raw) > max_bytes:
            return api_response(400, {'error': 'Template file must be between 1 byte and 5 MB'})

        bucket = os.environ.get('CAMPAIGN_ASSETS_BUCKET')
        if not bucket:
            raise RuntimeError('CAMPAIGN_ASSETS_BUCKET is not configured')

        ext = allowed_types[content_type]
        safe_name = re.sub(r'[^A-Za-z0-9_.-]', '-', name).strip('-') or 'template'
        timestamp = utc_now_iso().replace(':', '-')
        key = f'templates/uploads/{safe_name}-{timestamp}.{ext}'

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=raw,
            ContentType=content_type,
            CacheControl='private, max-age=31536000',
            Metadata={
                'uploaded_by': request_actor(event) or '',
                'template_name': name,
                'source_filename': filename
            }
        )

        # Store template metadata in config
        templates = get_config_value('infographic_template_uploads') or []
        new_template = {
            'name': name,
            'filename': filename,
            's3_key': key,
            'content_type': content_type,
            'size_bytes': len(raw),
            'uploaded_at': utc_now_iso(),
            'uploaded_by': request_actor(event)
        }
        templates.append(new_template)
        config_table.put_item(Item={
            'configKey': 'infographic_template_uploads',
            'value': templates
        })

        # Generate presigned URL for immediate display
        try:
            new_template['url'] = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=3600
            )
        except Exception:
            new_template['url'] = None

        return api_response(201, {'template': new_template, 'templates': templates})
    except ValueError as e:
        return api_response(400, {'error': str(e)})
    except Exception as e:
        print(f"Error uploading infographic template: {e}")
        return api_response(500, {'error': str(e)})


def normalize_chart_config(config):
    config = config if isinstance(config, dict) else {}
    valid_days = {
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
    }
    day = str(config.get('day', 'monday')).lower()
    if day not in valid_days:
        day = 'monday'

    hour = parse_int_param(config.get('hour'), 0, 0, 23)
    default_campaign_day, default_campaign_hour = default_campaign_time(day, hour)
    campaign_day = str(config.get('campaign_day', default_campaign_day)).lower()
    if campaign_day not in valid_days:
        campaign_day = default_campaign_day

    return {
        'day': day,
        'hour': hour,
        'campaign_generation_enabled': parse_bool_param(
            config.get('campaign_generation_enabled'),
            True
        ),
        'campaign_day': campaign_day,
        'campaign_hour': parse_int_param(config.get('campaign_hour'), default_campaign_hour, 0, 23),
        'freeze_enabled': parse_bool_param(config.get('freeze_enabled'), True)
    }


def default_campaign_time(reset_day, reset_hour):
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    campaign_hour = reset_hour - 2
    if campaign_hour >= 0:
        return reset_day, campaign_hour
    previous_day = days[(days.index(reset_day) - 1) % len(days)]
    return previous_day, campaign_hour + 24


def normalize_verification_sources(config):
    config = config if isinstance(config, dict) else {}
    spotify_validation_default = os.environ.get(
        'ENABLE_SPOTIFY_VALIDATION',
        os.environ.get('ENABLE_SPOTIFY', 'false')
    ).lower() == 'true'
    return {
        'musicbrainz_enabled': parse_bool_param(config.get('musicbrainz_enabled'), True),
        'spotify_validation_enabled': parse_bool_param(
            config.get('spotify_validation_enabled'),
            spotify_validation_default
        )
    }


def health_check(event):
    """Health check endpoint"""
    return api_response(200, {
        'status': 'healthy',
        'service': 'muddys-top10-api'
    })


def generate_pkce_pair():
    """Generate PKCE code verifier and challenge"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge


def spotify_feature_enabled():
    return os.environ.get(
        'ENABLE_SPOTIFY_PLAYLISTS',
        os.environ.get('ENABLE_SPOTIFY', 'false')
    ).lower() == 'true'


def spotify_disabled_response():
    return api_response(403, {
        'enabled': False,
        'connected': False,
        'error': 'Spotify feature is disabled'
    })


def spotify_connect(event):
    """Initiate Spotify OAuth flow"""
    try:
        if not spotify_feature_enabled():
            return spotify_disabled_response()

        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        if not client_id:
            return api_response(500, {'error': 'Spotify client ID not configured'})

        # Get API Gateway URL (this is where the callback will go)
        headers = event.get('headers', {})
        host = headers.get('Host') or headers.get('host', '')
        protocol = headers.get('X-Forwarded-Proto') or headers.get('x-forwarded-proto', 'https')

        # Store the CloudFront origin so we can redirect back after OAuth
        referer = headers.get('Referer') or headers.get('referer', '')
        if referer:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            frontend_origin = f"{parsed.scheme}://{parsed.netloc}"
        else:
            frontend_origin = None

        # Build redirect URI (API Gateway URL)
        api_path = event.get('requestContext', {}).get('path', '/Prod/api/spotify/callback')
        if '/api/spotify/connect' in api_path:
            api_path = api_path.replace('/api/spotify/connect', '/api/spotify/callback')

        redirect_uri = f"{protocol}://{host}{api_path}"

        # Generate PKCE pair
        state = secrets.token_urlsafe(32)
        code_verifier, code_challenge = generate_pkce_pair()

        # Store verifier with state and frontend origin (in production, use DynamoDB with TTL)
        oauth_state_store[state] = {
            'code_verifier': code_verifier,
            'frontend_origin': frontend_origin
        }

        # Build authorization URL
        auth_params = {
            'client_id': client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': 'playlist-modify-public playlist-modify-private ugc-image-upload',
            'code_challenge_method': 'S256',
            'code_challenge': code_challenge,
            'state': state
        }

        print(f"OAuth redirect_uri: {redirect_uri}")
        print(f"Frontend origin: {frontend_origin}")

        auth_url = f"https://accounts.spotify.com/authorize?{urlencode(auth_params)}"

        query_params = event.get('queryStringParameters') or {}
        if query_params.get('response') == 'json':
            return api_response(200, {'auth_url': auth_url})

        # Return redirect
        return {
            'statusCode': 302,
            'headers': {
                'Location': auth_url,
                'Access-Control-Allow-Origin': '*'
            },
            'body': ''
        }

    except Exception as e:
        print(f"Error initiating Spotify OAuth: {e}")
        import traceback
        traceback.print_exc()
        return api_response(500, {'error': str(e)})


def spotify_callback(event):
    """Handle Spotify OAuth callback"""
    try:
        if not spotify_feature_enabled():
            return {
                'statusCode': 302,
                'headers': {
                    'Location': '/admin.html?spotify_error=spotify_disabled',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': ''
            }

        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        code = query_params.get('code')
        state = query_params.get('state')
        error = query_params.get('error')

        if error:
            # Try to get frontend origin from state if available
            frontend_origin = None
            if state:
                state_data = oauth_state_store.get(state)
                if state_data and isinstance(state_data, dict):
                    frontend_origin = state_data.get('frontend_origin')

            # Redirect to admin panel with error
            if frontend_origin:
                redirect_location = f"{frontend_origin}/admin.html?spotify_error={error}"
            else:
                redirect_location = f'/admin.html?spotify_error={error}'

            return {
                'statusCode': 302,
                'headers': {
                    'Location': redirect_location,
                    'Access-Control-Allow-Origin': '*'
                },
                'body': ''
            }

        if not code or not state:
            return api_response(400, {'error': 'Missing code or state parameter'})

        # Get code verifier and frontend origin from state
        state_data = oauth_state_store.get(state)
        if not state_data:
            return api_response(400, {'error': 'Invalid or expired state parameter'})

        if isinstance(state_data, str):
            # Old format (backwards compatibility)
            code_verifier = state_data
            frontend_origin = None
        else:
            # New format
            code_verifier = state_data.get('code_verifier')
            frontend_origin = state_data.get('frontend_origin')

        # Clean up state
        del oauth_state_store[state]

        # Get credentials
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

        if not client_id or not client_secret:
            return api_response(500, {'error': 'Spotify credentials not configured'})

        # Build redirect URI - must match what was sent to Spotify
        headers = event.get('headers', {})
        host = headers.get('Host') or headers.get('host', '')
        protocol = headers.get('X-Forwarded-Proto') or headers.get('x-forwarded-proto', 'https')

        api_path = event.get('requestContext', {}).get('path', '/Prod/api/spotify/callback')

        redirect_uri = f"{protocol}://{host}{api_path}"

        # Exchange code for tokens
        import urllib3
        http = urllib3.PoolManager()

        credentials = f"{client_id}:{client_secret}"
        credentials_b64 = base64.b64encode(credentials.encode()).decode()

        token_data = urlencode({
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': code_verifier
        })

        response = http.request(
            'POST',
            'https://accounts.spotify.com/api/token',
            headers={
                'Authorization': f'Basic {credentials_b64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body=token_data
        )

        if response.status != 200:
            error_body = response.data.decode('utf-8')
            print(f"Token exchange error: {error_body}")
            return {
                'statusCode': 302,
                'headers': {
                    'Location': '/admin.html?spotify_error=token_exchange_failed',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': ''
            }

        tokens = json.loads(response.data.decode('utf-8'))
        refresh_token = tokens.get('refresh_token')

        if not refresh_token:
            print("No refresh token in response")
            return {
                'statusCode': 302,
                'headers': {
                    'Location': '/admin.html?spotify_error=no_refresh_token',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': ''
            }

        # Store refresh token in Secrets Manager
        secret_name = os.environ.get('SPOTIFY_REFRESH_TOKEN_SECRET')
        secrets_client.update_secret(
            SecretId=secret_name,
            SecretString=json.dumps({'refresh_token': refresh_token})
        )

        print("Successfully stored Spotify refresh token")

        # Redirect back to frontend (CloudFront) with success
        if frontend_origin:
            redirect_location = f"{frontend_origin}/admin.html?spotify_connected=true"
        else:
            # Fallback to relative path
            redirect_location = '/admin.html?spotify_connected=true'

        return {
            'statusCode': 302,
            'headers': {
                'Location': redirect_location,
                'Access-Control-Allow-Origin': '*'
            },
            'body': ''
        }

    except Exception as e:
        print(f"Error handling Spotify callback: {e}")
        import traceback
        traceback.print_exc()

        # Try to get frontend origin from Referer
        headers = event.get('headers', {})
        referer = headers.get('Referer') or headers.get('referer', '')
        if referer:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            frontend_origin = f"{parsed.scheme}://{parsed.netloc}"
            redirect_location = f"{frontend_origin}/admin.html?spotify_error=callback_failed"
        else:
            redirect_location = f'/admin.html?spotify_error=callback_failed'

        return {
            'statusCode': 302,
            'headers': {
                'Location': redirect_location,
                'Access-Control-Allow-Origin': '*'
            },
            'body': ''
        }


def spotify_status(event):
    """Check Spotify connection status"""
    try:
        if not spotify_feature_enabled():
            return api_response(200, {
                'enabled': False,
                'connected': False,
                'message': 'Spotify feature is disabled'
            })

        secret_name = os.environ.get('SPOTIFY_REFRESH_TOKEN_SECRET')

        # Try to get the secret
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response['SecretString'])
        refresh_token = secret_data.get('refresh_token', '')

        # Check if token is configured (not placeholder)
        is_connected = refresh_token and refresh_token != 'PLACEHOLDER_UPDATE_AFTER_AUTHORIZATION'

        return api_response(200, {
            'enabled': True,
            'connected': is_connected,
            'message': 'Spotify connected' if is_connected else 'Spotify not connected'
        })

    except Exception as e:
        print(f"Error checking Spotify status: {e}")
        return api_response(500, {'error': str(e)})


def spotify_disconnect(event):
    """Disconnect Spotify by resetting the refresh token"""
    try:
        if not spotify_feature_enabled():
            return spotify_disabled_response()

        secret_name = os.environ.get('SPOTIFY_REFRESH_TOKEN_SECRET')

        # Reset token to placeholder
        secrets_client.update_secret(
            SecretId=secret_name,
            SecretString=json.dumps({'refresh_token': 'PLACEHOLDER_UPDATE_AFTER_AUTHORIZATION'})
        )

        print("Successfully disconnected Spotify")

        return api_response(200, {
            'message': 'Spotify disconnected successfully'
        })

    except Exception as e:
        print(f"Error disconnecting Spotify: {e}")
        import traceback
        traceback.print_exc()
        return api_response(500, {'error': str(e)})


def spotify_generate_playlist(event):
    """Manually trigger playlist generation"""
    try:
        if not spotify_feature_enabled():
            return spotify_disabled_response()

        # Invoke the playlist generator Lambda
        lambda_client = boto3.client('lambda')

        function_name = os.environ.get('TRACKS_TABLE', 'muddys-top10-tracks').replace('-tracks', '-playlist-generator')

        print(f"Invoking playlist generator: {function_name}")

        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )

        # Parse response
        payload = json.loads(response['Payload'].read())
        status_code = payload.get('statusCode', 500)
        body = json.loads(payload.get('body', '{}'))

        if status_code == 200:
            return api_response(200, {
                'message': 'Playlist generated successfully',
                'playlist_url': body.get('playlist_url'),
                'tracks_added': body.get('tracks_added')
            })
        else:
            return api_response(status_code, {
                'error': body.get('error', 'Failed to generate playlist')
            })

    except Exception as e:
        print(f"Error generating playlist: {e}")
        import traceback
        traceback.print_exc()
        return api_response(500, {'error': str(e)})


def request_actor(event):
    claims = (
        event.get('requestContext', {})
        .get('authorizer', {})
        .get('claims', {})
    )
    return claims.get('email') or claims.get('cognito:username') or claims.get('sub')


def parse_json_body(event):
    try:
        return json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        raise ValueError('Request body must be valid JSON')


def parse_campaign_sections(value):
    if not value:
        return ['radio', 'infographic', 'social']
    if isinstance(value, str):
        value = [value]
    allowed = {'radio', 'infographic', 'social'}
    sections = [section for section in value if section in allowed]
    if not sections:
        raise ValueError('sections must include one of: radio, infographic, social')
    return sections


def get_campaign_week_id_from_event(event):
    path_params = event.get('pathParameters') or {}
    week_id = path_params.get('week_id') or path_params.get('week')
    if week_id:
        return week_id if valid_campaign_week_id(week_id) else None

    path = event.get('path', '')
    for prefix in ('/api/campaigns/',):
        if path.startswith(prefix):
            week_id = path[len(prefix):].strip('/').split('/')[0]
            return week_id if valid_campaign_week_id(week_id) else None
    return None


def get_campaign_revision_id_from_event(event):
    path = event.get('path', '')
    match = re.fullmatch(r'/api/campaigns/(\d{4}-\d{2}-\d{2})/revisions/([A-Za-z0-9_-]{1,64})', path)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def get_campaign_revision_feedback_ids_from_event(event):
    path = event.get('path', '')
    match = re.fullmatch(r'/api/campaigns/(\d{4}-\d{2}-\d{2})/revisions/([A-Za-z0-9_-]{1,64})/feedback', path)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def campaign_list(event):
    try:
        query_params = event.get('queryStringParameters') or {}
        limit = parse_int_param(query_params.get('limit'), 20, 1, 100)
        next_token = query_params.get('next_token')
        return api_response(200, load_campaigns(campaigns_table, limit, next_token))
    except Exception as e:
        print(f"Error listing campaigns: {e}")
        return api_response(500, {'error': str(e)})


def campaign_get(event):
    try:
        week_id = get_campaign_week_id_from_event(event)
        if not week_id:
            return api_response(400, {'error': 'Week must be in YYYY-MM-DD format'})

        campaign = load_campaign(campaigns_table, week_id)
        if not campaign:
            return api_response(404, {'error': 'Campaign not found', 'week_id': week_id})
        return api_response(200, {'campaign': enrich_campaign_asset_urls(campaign)})
    except Exception as e:
        print(f"Error getting campaign: {e}")
        return api_response(500, {'error': str(e)})


def campaign_diagnostics(event):
    try:
        week_id = get_campaign_week_id_from_event(event)
        if not week_id:
            return api_response(400, {'error': 'Week must be in YYYY-MM-DD format'})

        campaign = load_campaign(campaigns_table, week_id)
        if not campaign:
            return api_response(404, {'error': 'Campaign not found', 'week_id': week_id})

        events = fetch_campaign_log_events(campaign)
        analysis = analyze_campaign_failure(campaign, events)
        return api_response(200, {
            'week_id': week_id,
            'status': campaign.get('status'),
            'failure': campaign.get('failure'),
            'campaign_progress': campaign.get('campaign_progress'),
            'analysis': analysis,
            'logs': events
        })
    except Exception as e:
        print(f"Error loading campaign diagnostics: {e}")
        return api_response(500, {'error': str(e)})


def fetch_campaign_log_events(campaign):
    function_names = [
        os.environ.get('AWS_LAMBDA_FUNCTION_NAME'),
        os.environ.get('CAMPAIGN_GENERATOR_FUNCTION_NAME'),
        stack_function_name('agentcore-tools'),
        stack_function_name('infographic-renderer')
    ]
    log_groups = [
        f'/aws/lambda/{name}'
        for name in dict.fromkeys(function_names)
        if name
    ]
    start_ms, end_ms = diagnostics_time_window(campaign)
    events = []
    for log_group in log_groups:
        try:
            events.extend(fetch_log_group_events(
                log_group,
                start_ms,
                end_ms,
                '?ERROR ?Error ?Exception ?Traceback ?failed ?FAILED ?RuntimeClientError ?AccessDenied ?Timeout ?Task timed out ?Validation',
                'error'
            ))
        except Exception as e:
            events.append({
                'log_group': log_group,
                'timestamp': None,
                'type': 'diagnostics_error',
                'message': f'Unable to read log group: {e}'
            })
    if not any(event.get('type') == 'error' for event in events):
        for log_group in log_groups:
            try:
                events.extend(fetch_log_group_events(log_group, start_ms, end_ms, None, 'context', limit=15))
            except Exception:
                continue
    return sorted(events, key=lambda event: event.get('timestamp') or 0, reverse=True)[:50]


def fetch_log_group_events(log_group, start_ms, end_ms, filter_pattern, event_type, limit=25):
    args = {
        'logGroupName': log_group,
        'startTime': start_ms,
        'endTime': end_ms,
        'limit': limit
    }
    if filter_pattern:
        args['filterPattern'] = filter_pattern
    response = logs_client.filter_log_events(**args)
    return [
        {
            'log_group': log_group,
            'timestamp': event.get('timestamp'),
            'type': event_type,
            'message': compact_log_message(event.get('message') or '')
        }
        for event in response.get('events', [])
    ]


def diagnostics_time_window(campaign):
    timestamps = [
        campaign.get('generated_at'),
        (campaign.get('campaign_progress') or {}).get('updated_at'),
        campaign.get('approved_at'),
        campaign.get('reviewed_at')
    ]
    parsed = [
        parse_iso_timestamp_ms(value)
        for value in timestamps
        if value
    ]
    anchor = max(parsed) if parsed else int(datetime.now(timezone.utc).timestamp() * 1000)
    return anchor - (30 * 60 * 1000), anchor + (10 * 60 * 1000)


def parse_iso_timestamp_ms(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return int(parsed.timestamp() * 1000)
    except Exception:
        return None


def stack_function_name(suffix):
    name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or ''
    if not name.endswith('-api'):
        return None
    return name[:-4] + f'-{suffix}'


def compact_log_message(message):
    text = redact_log_message(re.sub(r'\s+', ' ', str(message)).strip())
    return text[:1000]


def redact_log_message(message):
    text = str(message)
    text = re.sub(r'Bearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]', text, flags=re.IGNORECASE)
    text = re.sub(r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_ACCESS_KEY]', text)
    text = re.sub(r'ASIA[0-9A-Z]{16}', '[REDACTED_AWS_ACCESS_KEY]', text)
    text = re.sub(r'(?i)(secretaccesskey|sessiontoken|authorization|x-amz-security-token)["\':= ]+[^,\s"}]+', r'\1=[REDACTED]', text)
    text = re.sub(r'X-Amz-Signature=[A-Fa-f0-9]+', 'X-Amz-Signature=[REDACTED]', text)
    text = re.sub(r'([A-Za-z0-9+/]{120,}={0,2})', '[REDACTED_LONG_TOKEN]', text)
    return text


def analyze_campaign_failure(campaign, events):
    text = ' '.join([
        str((campaign.get('failure') or {}).get('error') or ''),
        str((campaign.get('failure') or {}).get('message') or ''),
        ' '.join(event.get('message') or '' for event in events)
    ]).lower()
    if campaign_has_generated_assets(campaign) and campaign.get('status') == 'failed':
        return {
            'summary': 'Campaign assets exist, so generation likely completed and a later wrapper/progress step marked the campaign as failed.',
            'likely_cause': 'post_generation_status_mismatch',
            'recommended_action': 'Treat the generated assets as usable, then inspect the generation log context for the late failure.',
            'analysis_mode': 'deterministic'
        }
    if not text.strip():
        return {
            'summary': 'No failure details or matching error log events were found in the inspected time window.',
            'likely_cause': 'unknown',
            'recommended_action': 'Inspect logs around the campaign generation time and review the content generation plus image rendering steps.',
            'analysis_mode': 'deterministic'
        }
    rules = [
        ('access_denied', ['accessdenied', 'not authorized', 'no identity-based policy'], 'A generation step is missing permission for one of its downstream calls.', 'Check permissions for the named action/resource in the log message, then redeploy the policy fix.'),
        ('agentcore_runtime_init', ['runtime initialization time exceeded'], 'The campaign generation worker did not start within the service timeout.', 'Reduce startup cost or move heavy work out of startup; retry after the worker update stabilizes.'),
        ('agentcore_response_envelope', ['agentcore raw response excerpt', '"status": "success"', '"ok": true', '"tooluseid"'], 'The campaign was generated successfully, but the outer job misread the success response and marked it as failed.', 'Deploy the response parser fix, then regenerate. Existing generated assets can be treated as usable if they are present.'),
        ('agentcore_invoke', ['invokeagentruntime', 'agentcore runtime'], 'The campaign generator failed while invoking or reading the content generation response.', 'Inspect generation logs for the raw response and any tool error.'),
        ('renderer_timeout', ['task timed out', 'timeout', 'timed out'], 'A generation or render step timed out.', 'Check whether model generation or Playwright rendering exceeded the Lambda timeout; consider increasing timeout or reducing prompt/render complexity.'),
        ('throttling', ['throttlingexception', 'toomanyrequestsexception', 'rate exceeded', 'provisionedthroughputexceededexception'], 'An AWS service or model endpoint throttled the campaign job.', 'Retry after the throttle window, then consider reserved/concurrency/capacity limits if this repeats.'),
        ('bad_request', ['validationexception', 'parameter validation failed'], 'A generation step received an invalid request.', 'Inspect the nearest request/validation log and fix the payload or config value named there.'),
        ('missing_resource', ['resourcenotfoundexception', 'nosuchkey', 'not found'], 'A referenced prompt, source snapshot, image, or generated asset was missing.', 'Check the referenced resource name/key and verify it exists in the current environment.'),
        ('infographic_validation', ['infographic asset validation failed', 'validation failed'], 'The generated infographic HTML/CSS failed validation before rendering.', 'Review `infographic_asset_validation.errors`, adjust the prompt/template, then regenerate.'),
        ('renderer_missing_png', ['infographic renderer did not return', 'renderer failed'], 'The image rendering step did not return valid PNG metadata.', 'Inspect image rendering logs for browser or asset storage failures.'),
        ('renderer_browser', ['playwright', 'chromium', 'browsertype.launch'], 'The PNG rendering browser failed.', 'Inspect image rendering logs for missing browser binaries or incompatible runtime dependencies.'),
        ('model_or_mantle', ['bedrock mantle', 'invoke_model', 'model output', 'jsondecodeerror', 'invalid json'], 'Model generation returned an error or invalid JSON.', 'Inspect generation logs for the model response/error; adjust prompt/model settings if needed.'),
        ('s3_failure', ['s3', 'putobject', 'getobject', 'nosuchkey'], 'An S3 read/write failed for campaign assets.', 'Check campaign assets bucket permissions and whether referenced logo/template/PNG keys exist.'),
        ('campaign_write_conflict', ['conditionalcheckfailedexception'], 'Campaign persistence hit a DynamoDB conditional write conflict.', 'Check whether immutable campaign protection or a concurrent regeneration wrote the same campaign/revision.')
    ]
    for code, needles, summary, action in rules:
        if any(needle in text for needle in needles):
            return {
                'summary': summary,
                'likely_cause': code,
                'recommended_action': action,
                'analysis_mode': 'deterministic'
            }
    ai_analysis = ai_campaign_failure_analysis(campaign, events)
    if ai_analysis:
        return ai_analysis
    return {
        'summary': 'A campaign generation error was found, but it did not match a known failure pattern.',
        'likely_cause': 'unclassified',
        'recommended_action': 'Review the log excerpts below, starting with the newest generation or image rendering error.',
        'analysis_mode': 'deterministic'
    }


def campaign_has_generated_assets(campaign):
    return any(bool(campaign.get(field)) for field in (
        'active_revision_id',
        'infographic_png',
        'infographic_asset',
        'radio_reads',
        'social'
    ))


def ai_campaign_failure_analysis(campaign, events):
    model_id = os.environ.get('CAMPAIGN_DIAGNOSTICS_MODEL_ID', '').strip()
    if not model_id:
        return None
    relevant_events = events[:20]
    prompt = {
        'instruction': (
            'You are diagnosing a failed Muddy Top 10 campaign generation job. '
            'Use only the supplied status, failure object, and redacted logs. '
            'Return concise JSON with keys: likely_cause, confidence, human_summary, recommended_action, evidence. '
            'Do not mention CloudFormation or deployment unless it is explicitly present in the logs.'
        ),
        'campaign': {
            'week_id': campaign.get('week_id'),
            'status': campaign.get('status'),
            'has_active_revision': bool(campaign.get('active_revision_id')),
            'has_infographic_png': bool(campaign.get('infographic_png')),
            'has_infographic_asset': bool(campaign.get('infographic_asset')),
            'has_radio_reads': bool(campaign.get('radio_reads')),
            'has_social': bool(campaign.get('social')),
            'progress': campaign.get('campaign_progress'),
            'failure': campaign.get('failure')
        },
        'logs': relevant_events
    }
    try:
        model = BedrockCampaignModel(
            model_id=model_id,
            endpoint=os.environ.get('CAMPAIGN_DIAGNOSTICS_MODEL_ENDPOINT', os.environ.get('CAMPAIGN_MODEL_ENDPOINT', 'bedrock-mantle')),
            max_tokens=os.environ.get('CAMPAIGN_DIAGNOSTICS_MODEL_MAX_TOKENS', '700'),
            temperature=os.environ.get('CAMPAIGN_DIAGNOSTICS_MODEL_TEMPERATURE', '0.1'),
            project_id=os.environ.get('CAMPAIGN_DIAGNOSTICS_MODEL_PROJECT_ID', '').strip() or None,
            read_timeout=os.environ.get('CAMPAIGN_DIAGNOSTICS_MODEL_READ_TIMEOUT_SECONDS', '30'),
            api_key_secret_arn=os.environ.get('CAMPAIGN_DIAGNOSTICS_MODEL_API_KEY_SECRET_ARN', '').strip() or None
        )
        result = model.complete_json(json.dumps(prompt, default=str))
        return {
            'summary': str(result.get('human_summary') or result.get('summary') or 'AI reviewed the redacted logs but did not provide a summary.'),
            'likely_cause': str(result.get('likely_cause') or 'ai_unclassified_runtime_failure'),
            'recommended_action': str(result.get('recommended_action') or 'Review the evidence and rerun the campaign if the generated assets are incomplete.'),
            'confidence': str(result.get('confidence') or 'low'),
            'evidence': result.get('evidence') if isinstance(result.get('evidence'), list) else [],
            'analysis_mode': 'ai_assisted'
        }
    except Exception as e:
        print(f"AI campaign diagnostics failed: {e}")
        return None


def campaign_revision_list(event):
    try:
        week_id = get_campaign_week_id_from_event(event)
        if not week_id:
            return api_response(400, {'error': 'Week must be in YYYY-MM-DD format'})
        query_params = event.get('queryStringParameters') or {}
        limit = parse_int_param(query_params.get('limit'), 50, 1, 100)
        revisions = load_campaign_revisions(campaigns_table, week_id, limit)
        return api_response(200, {
            'week_id': week_id,
            'revisions': revisions,
            'count': len(revisions)
        })
    except Exception as e:
        print(f"Error listing campaign revisions: {e}")
        return api_response(500, {'error': str(e)})


def campaign_revision_get(event):
    try:
        week_id, revision_id = get_campaign_revision_id_from_event(event)
        if not week_id or not revision_id:
            return api_response(400, {'error': 'Revision path must be /api/campaigns/YYYY-MM-DD/revisions/REVISION_ID'})

        revision = load_campaign_revision(campaigns_table, week_id, revision_id)
        if not revision:
            return api_response(404, {'error': 'Campaign revision not found', 'week_id': week_id, 'revision_id': revision_id})
        return api_response(200, {'revision': enrich_campaign_asset_urls(revision)})
    except Exception as e:
        print(f"Error getting campaign revision: {e}")
        return api_response(500, {'error': str(e)})


def campaign_revision_approve(event):
    try:
        week_id, revision_id = get_campaign_revision_id_from_event(event)
        if not week_id or not revision_id:
            return api_response(400, {'error': 'Revision path must be /api/campaigns/YYYY-MM-DD/revisions/REVISION_ID'})

        campaign = approve_campaign_revision(
            campaigns_table,
            week_id,
            revision_id,
            actor=request_actor(event),
            timestamp=utc_now_iso()
        )
        return api_response(200, {'campaign': enrich_campaign_asset_urls(campaign)})
    except ValueError as e:
        return api_response(404, {'error': str(e)})
    except Exception as e:
        print(f"Error approving campaign revision: {e}")
        return api_response(500, {'error': str(e)})


def campaign_revision_feedback_list(event):
    try:
        week_id, revision_id = get_campaign_revision_feedback_ids_from_event(event)
        if not week_id or not revision_id:
            return api_response(400, {'error': 'Feedback path must be /api/campaigns/YYYY-MM-DD/revisions/REVISION_ID/feedback'})
        query_params = event.get('queryStringParameters') or {}
        limit = parse_int_param(query_params.get('limit'), 50, 1, 100)
        feedback = load_campaign_feedback(campaigns_table, week_id, revision_id, limit)
        return api_response(200, {
            'week_id': week_id,
            'revision_id': revision_id,
            'feedback': feedback,
            'count': len(feedback)
        })
    except Exception as e:
        print(f"Error listing campaign feedback: {e}")
        return api_response(500, {'error': str(e)})


def campaign_revision_feedback_put(event):
    try:
        week_id, revision_id = get_campaign_revision_feedback_ids_from_event(event)
        if not week_id or not revision_id:
            return api_response(400, {'error': 'Feedback path must be /api/campaigns/YYYY-MM-DD/revisions/REVISION_ID/feedback'})

        revision = load_campaign_revision(campaigns_table, week_id, revision_id)
        if not revision:
            return api_response(404, {'error': 'Campaign revision not found', 'week_id': week_id, 'revision_id': revision_id})

        body = parse_json_body(event)
        asset_type = body.get('asset_type')
        generator = revision.get('generator') or {}
        prompt_refs = generator.get('prompt_refs') or {}
        feedback = put_campaign_feedback(campaigns_table, {
            'week_id': week_id,
            'revision_id': revision_id,
            'asset_type': asset_type,
            'rating': body.get('rating'),
            'feedback_text': body.get('feedback_text'),
            'prompt_refs': prompt_refs_for_asset(asset_type, prompt_refs),
            'model_id': generator.get('model'),
            'created_at': utc_now_iso(),
            'created_by': request_actor(event)
        })

        # Write feedback to AgentCore Memory for future generation improvement
        remember_feedback(feedback)

        return api_response(201, {'feedback': feedback})
    except ValueError as e:
        return api_response(400, {'error': str(e)})
    except Exception as e:
        print(f"Error saving campaign feedback: {e}")
        return api_response(500, {'error': str(e)})


def campaign_feedback_summary(event):
    try:
        query_params = event.get('queryStringParameters') or {}
        limit = parse_int_param(query_params.get('limit'), 500, 1, 1000)
        feedback = list_all_campaign_feedback(campaigns_table, limit)
        summary = summarize_campaign_feedback(feedback)
        return api_response(200, {
            'limit': limit,
            'summary': summary
        })
    except Exception as e:
        print(f"Error summarizing campaign feedback: {e}")
        return api_response(500, {'error': str(e)})


def prompt_refs_for_asset(asset_type, prompt_refs):
    if asset_type == 'infographic':
        return {
            key: prompt_refs.get(key)
            for key in ('infographic', 'infographic_asset')
            if prompt_refs.get(key)
        }
    if asset_type == 'radio':
        return {
            'radio_reads': prompt_refs.get('radio_reads')
        } if prompt_refs.get('radio_reads') else {}
    if asset_type == 'social':
        return {
            'social': prompt_refs.get('social')
        } if prompt_refs.get('social') else {}
    return {}


def campaign_generate(event):
    try:
        body = parse_json_body(event)
        week_id = body.get('week_id')
        if week_id and not valid_campaign_week_id(week_id):
            return api_response(400, {'error': 'week_id must be in YYYY-MM-DD format'})

        sections = parse_campaign_sections(body.get('sections'))
        actor = request_actor(event)
        queued_week_id = week_id or latest_campaign_week_id()
        if not queued_week_id:
            return api_response(404, {'error': 'No Top 10 history snapshots are available for campaign generation'})

        put_campaign_progress(
            campaigns_table,
            queued_week_id,
            'queued',
            'Campaign request accepted and queued for background generation.',
            sections=sections,
            requested_by=actor,
            generated_by='human-request',
            timestamp=utc_now_iso()
        )
        invoke_campaign_generation_job({
            'week_id': queued_week_id,
            'sections': sections,
            'requested_by': actor,
            'generated_by': 'human-request'
        })

        return api_response(202, {
            'message': 'Campaign generation started',
            'week_id': queued_week_id,
            'sections': sections
        })
    except ValueError as e:
        return api_response(400, {'error': str(e)})
    except Exception as e:
        print(f"Error generating campaign: {e}")
        import traceback
        traceback.print_exc()
        return api_response(500, {'error': str(e)})


def invoke_campaign_generation_job(payload):
    function_name = os.environ.get('CAMPAIGN_GENERATOR_FUNCTION_NAME')
    if not function_name:
        raise RuntimeError('CAMPAIGN_GENERATOR_FUNCTION_NAME is not configured')

    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='Event',
        Payload=json.dumps(payload).encode('utf-8')
    )
    status_code = int(response.get('StatusCode', 0))
    if status_code < 200 or status_code >= 300:
        raise RuntimeError(f'Campaign generation job was not accepted: {status_code}')


def latest_campaign_week_id():
    response = chart_history_table.query(
        KeyConditionExpression=Key('pk').eq('TOP10_HISTORY'),
        ScanIndexForward=False,
        Limit=1
    )
    items = response.get('Items', [])
    return items[0].get('week_id') if items else None


def invoke_agentcore_campaign_runtime(payload):
    runtime_arn = os.environ.get('AGENTCORE_RUNTIME_ARN')
    if not runtime_arn:
        raise RuntimeError('AGENTCORE_RUNTIME_ARN is not configured')

    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        qualifier=os.environ.get('AGENTCORE_RUNTIME_QUALIFIER', 'DEFAULT'),
        runtimeSessionId=agentcore_runtime_session_id(payload, 'api'),
        contentType='application/json',
        accept='application/json',
        payload=json.dumps(payload).encode('utf-8')
    )
    raw_payload = read_agentcore_response(response)
    result = json.loads(raw_payload or '{}')
    if not result.get('ok', False):
        raise RuntimeError(result.get('error') or 'AgentCore Runtime campaign generation failed')
    return result


def agentcore_runtime_session_id(payload, source):
    week_id = payload.get('week_id') or 'latest'
    stack_hint = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'muddys-top10')
    safe_stack_hint = re.sub(r'[^A-Za-z0-9_-]', '-', stack_hint)[-24:]
    safe_week_id = re.sub(r'[^A-Za-z0-9_-]', '-', week_id)
    return f"muddys-campaign-{source}-{safe_stack_hint}-{safe_week_id}"


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


def campaign_update(event):
    try:
        week_id = get_campaign_week_id_from_event(event)
        if not week_id:
            return api_response(400, {'error': 'Week must be in YYYY-MM-DD format'})

        body = parse_json_body(event)
        actor = request_actor(event)
        campaign = update_campaign_content(
            campaigns_table,
            week_id,
            body,
            actor=actor,
            timestamp=utc_now_iso()
        )
        return api_response(200, {'campaign': enrich_campaign_asset_urls(campaign)})
    except ValueError as e:
        return api_response(400, {'error': str(e)})
    except Exception as e:
        print(f"Error updating campaign: {e}")
        return api_response(500, {'error': str(e)})


def campaign_delete(event):
    try:
        week_id = get_campaign_week_id_from_event(event)
        if not week_id:
            return api_response(400, {'error': 'Week must be in YYYY-MM-DD format'})

        deleted = delete_campaign_records(campaigns_table, week_id)
        if not deleted.get('campaign') and not deleted.get('revisions') and not deleted.get('feedback'):
            return api_response(404, {'error': 'Campaign not found', 'week_id': week_id})
        asset_cleanup = delete_campaign_owned_assets(deleted)

        return api_response(200, {
            'message': 'Campaign deleted',
            'week_id': week_id,
            'deleted_revision_count': deleted['deleted_revision_count'],
            'deleted_feedback_count': deleted['deleted_feedback_count'],
            'deleted_asset_count': asset_cleanup['deleted_count'],
            'asset_delete_errors': asset_cleanup['errors']
        })
    except Exception as e:
        print(f"Error deleting campaign: {e}")
        return api_response(500, {'error': str(e)})


def delete_campaign_owned_assets(deleted_records):
    seen = set()
    errors = []
    deleted_count = 0
    records = list(chain(
        [deleted_records.get('campaign')] if deleted_records.get('campaign') else [],
        deleted_records.get('revisions') or []
    ))
    for record in records:
        png = record.get('infographic_png') if isinstance(record, dict) else None
        if not isinstance(png, dict):
            continue
        bucket = png.get('bucket')
        key = png.get('key')
        if not bucket or not key or (bucket, key) in seen:
            continue
        seen.add((bucket, key))
        try:
            s3_client.delete_object(Bucket=bucket, Key=key)
            deleted_count += 1
        except Exception as e:
            errors.append({'bucket': bucket, 'key': key, 'error': str(e)})
    return {'deleted_count': deleted_count, 'errors': errors}


def campaign_status(event):
    try:
        week_id = get_campaign_week_id_from_event(event)
        if not week_id:
            return api_response(400, {'error': 'Week must be in YYYY-MM-DD format'})

        body = parse_json_body(event)
        status = body.get('status')
        allowed_statuses = {'draft', 'reviewed', 'approved', 'published'}
        if status not in allowed_statuses:
            return api_response(400, {'error': 'status must be one of: draft, reviewed, approved, published'})

        campaign = update_campaign_status(
            campaigns_table,
            week_id,
            status,
            actor=request_actor(event),
            timestamp=utc_now_iso()
        )
        return api_response(200, {'campaign': enrich_campaign_asset_urls(campaign)})
    except ValueError as e:
        return api_response(400, {'error': str(e)})
    except Exception as e:
        print(f"Error updating campaign status: {e}")
        return api_response(500, {'error': str(e)})


def enrich_campaign_asset_urls(campaign):
    png = campaign.get('infographic_png')
    if not isinstance(png, dict) or not png.get('bucket') or not png.get('key'):
        return campaign

    enriched = dict(campaign)
    enriched_png = dict(png)
    try:
        enriched_png['url'] = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': png['bucket'],
                'Key': png['key'],
                'ResponseContentType': png.get('content_type', 'image/png')
            },
            ExpiresIn=3600
        )
        enriched_png['download_url'] = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': png['bucket'],
                'Key': png['key'],
                'ResponseContentType': png.get('content_type', 'image/png'),
                'ResponseContentDisposition': f'attachment; filename="muddys-top10-{campaign.get("week_id", "campaign")}.png"'
            },
            ExpiresIn=3600
        )
    except Exception as e:
        print(f"Failed to presign campaign infographic PNG: {e}")
        enriched_png['url_error'] = str(e)
    enriched['infographic_png'] = enriched_png
    return enriched


def lambda_handler(event, context):
    """Main Lambda handler"""
    print(f"Event: {json.dumps(event)}")

    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')

    # Route requests
    try:
        if path == '/api/history' and method == 'GET':
            return get_history(event)
        elif path == '/api/top10' and method == 'GET':
            return get_top10(event)
        elif path == '/api/top10/history' and method == 'GET':
            return get_top10_history(event)
        elif path.startswith('/api/top10/history/') and method == 'GET':
            return get_top10_history_week(event)
        elif path == '/api/config' and method == 'GET':
            return get_config(event)
        elif path == '/api/config' and method == 'PUT':
            return put_config(event)
        elif path == '/api/config/logo' and method == 'PUT':
            return put_campaign_logo(event)
        elif path == '/api/config/infographic-template/reference' and method == 'POST':
            return post_infographic_template_reference(event)
        elif path == '/api/config/infographic-templates' and method == 'GET':
            return list_infographic_templates(event)
        elif path == '/api/config/infographic-templates' and method == 'POST':
            return upload_infographic_template(event)
        elif path == '/api/health' and method == 'GET':
            return health_check(event)
        elif path == '/api/spotify/connect' and method == 'GET':
            return spotify_connect(event)
        elif path == '/api/spotify/callback' and method == 'GET':
            return spotify_callback(event)
        elif path == '/api/spotify/status' and method == 'GET':
            return spotify_status(event)
        elif path == '/api/spotify/generate-playlist' and method == 'POST':
            return spotify_generate_playlist(event)
        elif path == '/api/spotify/disconnect' and method == 'POST':
            return spotify_disconnect(event)
        elif path == '/api/campaigns' and method == 'GET':
            return campaign_list(event)
        elif path == '/api/campaigns/generate' and method == 'POST':
            return campaign_generate(event)
        elif path == '/api/campaigns/feedback/summary' and method == 'GET':
            return campaign_feedback_summary(event)
        elif re.fullmatch(r'/api/campaigns/\d{4}-\d{2}-\d{2}/revisions/[A-Za-z0-9_-]{1,64}/feedback', path) and method == 'GET':
            return campaign_revision_feedback_list(event)
        elif re.fullmatch(r'/api/campaigns/\d{4}-\d{2}-\d{2}/revisions/[A-Za-z0-9_-]{1,64}/feedback', path) and method == 'POST':
            return campaign_revision_feedback_put(event)
        elif re.fullmatch(r'/api/campaigns/\d{4}-\d{2}-\d{2}/revisions/[A-Za-z0-9_-]{1,64}/approve', path) and method == 'PUT':
            return campaign_revision_approve(event)
        elif re.fullmatch(r'/api/campaigns/\d{4}-\d{2}-\d{2}/revisions/[A-Za-z0-9_-]{1,64}', path) and method == 'GET':
            return campaign_revision_get(event)
        elif re.fullmatch(r'/api/campaigns/\d{4}-\d{2}-\d{2}/revisions', path) and method == 'GET':
            return campaign_revision_list(event)
        elif path.startswith('/api/campaigns/') and path.endswith('/status') and method == 'PUT':
            return campaign_status(event)
        elif path.startswith('/api/campaigns/') and path.endswith('/diagnostics') and method == 'GET':
            return campaign_diagnostics(event)
        elif path.startswith('/api/campaigns/') and method == 'DELETE':
            return campaign_delete(event)
        elif path.startswith('/api/campaigns/') and method == 'GET':
            return campaign_get(event)
        elif path.startswith('/api/campaigns/') and method == 'PUT':
            return campaign_update(event)
        else:
            return api_response(404, {'error': 'Not found'})
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return api_response(500, {'error': 'Internal server error', 'message': str(e)})
