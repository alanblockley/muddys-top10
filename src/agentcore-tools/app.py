"""
AgentCore Gateway Lambda target for Muddy's chart campaign tools.

AgentCore passes tool arguments as the Lambda event and the selected tool name
in context.client_context.custom.bedrockAgentCoreToolName.
"""
import json
import os
import base64
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

from campaign_generation import (
    create_campaign_draft,
    generate_infographic_content,
    generate_radio_reads,
    generate_social_posts,
    merge_regenerated_sections,
    utc_now_iso,
    venue_config_with_branding,
)
from campaign_store import (
    create_chart_brief_from_history,
    get_campaign,
    get_latest_snapshot,
    get_snapshot,
    list_campaigns,
    put_campaign_with_revision,
    update_campaign_status,
    update_campaign_progress,
    valid_week_id,
)
from chart_brief import history_index_item, public_snapshot
from infographic_templates import resolve_template


dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
s3_client = boto3.client('s3')
chart_history_table = dynamodb.Table(os.environ['CHART_HISTORY_TABLE'])
campaigns_table = dynamodb.Table(os.environ['CAMPAIGNS_TABLE'])
config_table = dynamodb.Table(os.environ['CONFIG_TABLE'])


def lambda_handler(event, context):
    print(f"AgentCore tool event: {json.dumps(event)}")
    tool_name = resolve_tool_name(event, context)

    try:
        result = dispatch_tool(tool_name, event or {})
        return {
            'ok': True,
            'tool': tool_name,
            **result
        }
    except ValueError as e:
        return {
            'ok': False,
            'tool': tool_name,
            'error': str(e)
        }
    except Exception as e:
        print(f"AgentCore tool error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'tool': tool_name,
            'error': str(e)
        }


def resolve_tool_name(event, context):
    explicit = (event or {}).get('tool') or (event or {}).get('tool_name')
    if explicit:
        return strip_gateway_prefix(explicit)

    client_context = getattr(context, 'client_context', None)
    custom = getattr(client_context, 'custom', None) if client_context else None
    if custom and custom.get('bedrockAgentCoreToolName'):
        return strip_gateway_prefix(custom['bedrockAgentCoreToolName'])

    raise ValueError('Unable to resolve AgentCore tool name')


def strip_gateway_prefix(tool_name):
    delimiter = '___'
    if delimiter in tool_name:
        return tool_name.split(delimiter, 1)[1]
    return tool_name


def dispatch_tool(tool_name, args):
    if tool_name == 'get_current_chart':
        snapshot = get_latest_snapshot(chart_history_table)
        if not snapshot:
            raise ValueError('No chart snapshots are available')
        return {'snapshot': public_snapshot(snapshot)}

    if tool_name == 'list_chart_weeks':
        return list_chart_weeks(args)

    if tool_name == 'get_chart_week':
        week_id = require_week_id(args)
        snapshot = get_snapshot(chart_history_table, week_id)
        if not snapshot:
            raise ValueError(f'No chart snapshot found for {week_id}')
        return {'snapshot': public_snapshot(snapshot)}

    if tool_name == 'get_chart_range':
        return get_chart_range(args)

    if tool_name == 'create_chart_brief':
        week_id = optional_week_id(args)
        return {'chart_brief': create_chart_brief_from_history(chart_history_table, week_id)}

    if tool_name == 'create_radio_reads':
        chart_brief = create_chart_brief_from_history(chart_history_table, optional_week_id(args))
        return {'radio_reads': generate_radio_reads(chart_brief, current_venue_config())}

    if tool_name == 'create_infographic_content':
        chart_brief = create_chart_brief_from_history(chart_history_table, optional_week_id(args))
        return {'infographic': generate_infographic_content(chart_brief, current_venue_config())}

    if tool_name == 'create_social_posts':
        chart_brief = create_chart_brief_from_history(chart_history_table, optional_week_id(args))
        return {'social': generate_social_posts(chart_brief, current_venue_config())}

    if tool_name == 'create_chart_campaign':
        return create_chart_campaign(args)

    if tool_name == 'get_chart_campaign':
        week_id = require_week_id(args)
        campaign = get_campaign(campaigns_table, week_id)
        if not campaign:
            raise ValueError(f'No campaign found for {week_id}')
        return {'campaign': campaign}

    if tool_name == 'update_chart_campaign_status':
        week_id = require_week_id(args)
        status = args.get('status')
        if status not in {'draft', 'reviewed', 'approved', 'published'}:
            raise ValueError('status must be one of: draft, reviewed, approved, published')
        campaign = update_campaign_status(
            campaigns_table,
            week_id,
            status,
            actor=args.get('actor') or 'agentcore',
            timestamp=utc_now_iso()
        )
        return {'campaign': campaign}

    if tool_name == 'list_chart_campaigns':
        limit = parse_limit(args.get('limit'), 20, 100)
        return list_campaigns(campaigns_table, limit, args.get('next_token'))

    raise ValueError(f'Unknown AgentCore tool: {tool_name}')


def list_chart_weeks(args):
    query_args = {
        'KeyConditionExpression': Key('pk').eq('TOP10_HISTORY'),
        'ScanIndexForward': False,
        'Limit': parse_limit(args.get('limit'), 12, 104)
    }
    from_week = args.get('from_date') or args.get('from')
    to_week = args.get('to_date') or args.get('to')
    if from_week or to_week:
        validate_optional_week(from_week, 'from_date')
        validate_optional_week(to_week, 'to_date')
        query_args['KeyConditionExpression'] = (
            Key('pk').eq('TOP10_HISTORY') &
            Key('sk').between(f'WEEK#{from_week or "0000-01-01"}', f'WEEK#{to_week or "9999-12-31"}')
        )

    response = chart_history_table.query(**query_args)
    return {
        'weeks': [history_index_item(item) for item in response.get('Items', [])],
        'count': len(response.get('Items', []))
    }


def get_chart_range(args):
    from_week = args.get('from_date') or args.get('from')
    to_week = args.get('to_date') or args.get('to')
    validate_optional_week(from_week, 'from_date')
    validate_optional_week(to_week, 'to_date')
    if from_week and to_week and from_week > to_week:
        raise ValueError('from_date must be before or equal to to_date')

    query_args = {
        'KeyConditionExpression': (
            Key('pk').eq('TOP10_HISTORY') &
            Key('sk').between(f'WEEK#{from_week or "0000-01-01"}', f'WEEK#{to_week or "9999-12-31"}')
        ),
        'ScanIndexForward': False,
        'Limit': parse_limit(args.get('limit'), 12, 104)
    }
    response = chart_history_table.query(**query_args)
    return {
        'snapshots': [public_snapshot(item) for item in response.get('Items', [])],
        'count': len(response.get('Items', []))
    }


def create_chart_campaign(args):
    sections = parse_sections(args.get('sections'))
    week_id = optional_week_id(args)
    progress_week_id = week_id
    try:
        if progress_week_id:
            set_progress(progress_week_id, 'building_chart_brief', 'Building factual chart brief from Top 10 history.')
        chart_brief = create_chart_brief_from_history(chart_history_table, week_id)
        progress_week_id = chart_brief['week_id']
        set_progress(progress_week_id, 'generating_campaign_content', 'Generating campaign copy and infographic content.')
        generated = create_campaign_draft(
            chart_brief,
            sections=sections,
            venue_config=venue_config_with_branding(get_config_value('campaign_branding')),
            infographic_template=current_infographic_template(),
            prompt_config=get_config_value('campaign_prompts'),
            requested_by=args.get('requested_by'),
            generated_by=args.get('generated_by') or 'agentcore'
        )
        existing = get_campaign(campaigns_table, chart_brief['week_id'])
        parent_revision_id = existing.get('active_revision_id') if existing else None
        campaign = merge_regenerated_sections(existing, generated, sections) if existing else generated
        if 'infographic' in sections:
            # Skip infographic_asset validation for AntV path — the renderer
            # takes chart_data directly, no HTML/CSS asset needed
            validation = campaign.get('infographic_asset_validation') or {}
            if validation and not validation.get('valid', True):
                errors = validation.get('errors') or []
                # Only block on security errors, not content warnings
                security_errors = [e for e in errors if 'blocked content' in e]
                if security_errors:
                    raise RuntimeError(f"Infographic asset validation failed: {', '.join(security_errors)}")
            set_progress(progress_week_id, 'rendering_infographic_png', 'Rendering the final infographic PNG.')
            campaign['infographic_png'] = render_infographic_png(campaign, chart_brief=chart_brief)
        set_progress(progress_week_id, 'saving_campaign', 'Saving generated campaign assets and metadata.')
        campaign['campaign_progress'] = {
            'stage': 'complete',
            'message': 'Campaign generated successfully.',
            'updated_at': utc_now_iso()
        }
        put_campaign_with_revision(campaigns_table, campaign, parent_revision_id=parent_revision_id)
        return {'campaign': campaign}
    except Exception as e:
        if progress_week_id:
            set_progress(
                progress_week_id,
                'failed',
                f'Campaign generation failed: {e}',
                status='failed',
                error=e
            )
        raise


def set_progress(week_id, stage, message, status='processing', error=None):
    try:
        update_campaign_progress(
            campaigns_table,
            week_id,
            stage,
            message,
            status=status,
            timestamp=utc_now_iso(),
            error=error
        )
    except Exception as e:
        print(f"Failed to update campaign progress for {week_id}: {e}")


def render_infographic_png(campaign, chart_brief=None):
    """Render the infographic PNG via AntV chart data path."""
    function_name = os.environ.get('INFOGRAPHIC_RENDERER_FUNCTION_NAME')
    if not function_name:
        raise RuntimeError('INFOGRAPHIC_RENDERER_FUNCTION_NAME is not configured')

    chart_brief = chart_brief or campaign.get('chart_brief') or {}
    infographic = campaign.get('infographic') or {}
    branding = ((campaign.get('infographic_asset') or {}).get('metadata') or {}).get('brand_config_snapshot') or {}

    # Build the chart_data payload for the AntV renderer
    tracks = chart_brief.get('tracks', [])[:10]
    print(f"Infographic renderer: {len(tracks)} tracks from chart_brief for week {campaign.get('week_id')}")

    def format_week_display(week_id):
        """Format week_id (YYYY-MM-DD) as '25 July – 1 August 2026'."""
        if not week_id:
            return ''
        months = ['January','February','March','April','May','June','July','August','September','October','November','December']
        try:
            parts = str(week_id).split('-')
            start = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            end = start + timedelta(days=7)
            start_str = f"{start.day} {months[start.month - 1]}"
            if start.month == end.month and start.year == end.year:
                end_str = f"{end.day} {months[end.month - 1]} {end.year}"
            elif start.year == end.year:
                end_str = f"{end.day} {months[end.month - 1]} {end.year}"
            else:
                start_str = f"{start.day} {months[start.month - 1]} {start.year}"
                end_str = f"{end.day} {months[end.month - 1]} {end.year}"
            return f"{start_str} – {end_str}"
        except Exception:
            return f"Week of {week_id}"

    def extract_artist(track):
        if track.get('artist'):
            return track['artist']
        combined = track.get('track', '')
        return combined.split(' - ', 1)[0].strip() if ' - ' in combined else combined

    def extract_title(track):
        if track.get('title'):
            return track['title']
        combined = track.get('track', '')
        return combined.split(' - ', 1)[1].strip() if ' - ' in combined else ''

    chart_data = {
        'week_id': campaign.get('week_id', 'unknown'),
        'chart_title': branding.get('chart_title') or "Muddy's Top 10",
        'tagline': branding.get('tagline') or 'Your requests. Your music. Your chart.',
        'week_display': format_week_display(campaign.get('week_id', '')),
        'headline': infographic.get('headline') or infographic.get('chart_story', ''),
        'chart_story': infographic.get('chart_story') or '',
        'tracks': [
            {
                'rank': track.get('rank', i + 1),
                'artist': extract_artist(track),
                'title': extract_title(track),
                'plays': track.get('play_count') or track.get('plays', 0),
                'movement': track.get('movement', 'same'),
                'delta': track.get('movement_delta') or track.get('delta'),
            }
            for i, track in enumerate(tracks)
        ],
        'stats': {
            'new_entries': len([t for t in tracks if t.get('movement') == 'new']),
            'climbers': len([t for t in tracks if t.get('movement') == 'up']),
            'fallers': len([t for t in tracks if t.get('movement') == 'down']),
            'non_movers': len([t for t in tracks if t.get('movement') == 'same']),
        },
        'show': {
            'time': '2AM SLT',
            'day': 'EVERY SATURDAY',
            'presenters': 'DJ TOOHEY & JP'
        },
        'chart_talk': infographic.get('chart_talk') or []
    }

    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps({
            'chart_data': chart_data,
            'week_id': campaign.get('week_id')
        }).encode('utf-8')
    )
    raw_payload = response.get('Payload').read().decode('utf-8')
    result = json.loads(raw_payload or '{}')
    if response.get('FunctionError'):
        raise RuntimeError(result.get('errorMessage') or raw_payload or 'Infographic renderer failed')
    if not result.get('ok', False):
        raise RuntimeError(result.get('error') or 'Infographic renderer did not return ok')
    if not result.get('infographic_png'):
        raise RuntimeError('Infographic renderer did not return infographic_png metadata')
    return result['infographic_png']

def get_config_value(config_key):
    response = config_table.get_item(Key={'configKey': config_key})
    item = response.get('Item')
    return item.get('value') if item else None


def current_venue_config():
    return venue_config_with_branding(get_config_value('campaign_branding'))


def current_infographic_template():
    template = resolve_template(
        get_config_value('campaign_infographic_template'),
        s3_client=s3_client,
        bucket=os.environ.get('CAMPAIGN_ASSETS_BUCKET')
    )
    return attach_template_reference_image(template)


def attach_template_reference_image(template):
    bucket = os.environ.get('CAMPAIGN_ASSETS_BUCKET')
    key = template.get('reference_png_key')
    if not bucket or not key:
        return template
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        body = response['Body'].read()
        content_type = response.get('ContentType') or 'image/png'
        template['reference_image'] = {
            'bucket': bucket,
            'key': key,
            'content_type': content_type,
            'data_uri': f"data:{content_type};base64,{base64.b64encode(body).decode('ascii')}",
            'generated_at': template.get('reference_png_generated_at') or ''
        }
    except Exception as e:
        print(f"Unable to load infographic template reference image {key}: {e}")
    return template


def require_week_id(args):
    week_id = args.get('week_id')
    if not valid_week_id(week_id):
        raise ValueError('week_id must be in YYYY-MM-DD format')
    return week_id


def optional_week_id(args):
    week_id = args.get('week_id')
    if week_id and not valid_week_id(week_id):
        raise ValueError('week_id must be in YYYY-MM-DD format')
    return week_id


def validate_optional_week(value, name):
    if value and not valid_week_id(value):
        raise ValueError(f'{name} must be in YYYY-MM-DD format')


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


def parse_limit(value, default, maximum):
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(maximum, parsed))
