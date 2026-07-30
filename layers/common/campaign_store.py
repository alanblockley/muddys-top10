"""DynamoDB access helpers for chart campaign workflows."""
import base64
import json
import re
from copy import deepcopy
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from chart_brief import build_chart_brief, history_index_item, public_snapshot


def valid_week_id(value):
    return bool(value and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value))


def encode_page_token(last_evaluated_key):
    raw = json.dumps(last_evaluated_key)
    return base64.urlsafe_b64encode(raw.encode('utf-8')).decode('utf-8').rstrip('=')


def decode_page_token(token):
    padding = '=' * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + padding).encode('utf-8'))
    return json.loads(raw.decode('utf-8'))


def get_snapshot(chart_history_table, week_id):
    response = chart_history_table.get_item(
        Key={
            'pk': 'TOP10_HISTORY',
            'sk': f'WEEK#{week_id}'
        }
    )
    return response.get('Item')


def get_latest_snapshot(chart_history_table):
    response = chart_history_table.query(
        KeyConditionExpression=Key('pk').eq('TOP10_HISTORY'),
        ScanIndexForward=False,
        Limit=1
    )
    items = response.get('Items', [])
    return items[0] if items else None


def list_snapshots(chart_history_table, limit=104):
    response = chart_history_table.query(
        KeyConditionExpression=Key('pk').eq('TOP10_HISTORY'),
        ScanIndexForward=False,
        Limit=limit
    )
    return response.get('Items', [])


def list_snapshots_before(chart_history_table, week_id, limit=104):
    response = chart_history_table.query(
        KeyConditionExpression=(
            Key('pk').eq('TOP10_HISTORY') &
            Key('sk').lt(f'WEEK#{week_id}')
        ),
        ScanIndexForward=False,
        Limit=limit
    )
    return response.get('Items', [])


def create_chart_brief_from_history(chart_history_table, week_id=None, history_limit=104):
    current_snapshot = get_snapshot(chart_history_table, week_id) if week_id else get_latest_snapshot(chart_history_table)
    if not current_snapshot:
        raise ValueError('Top 10 history snapshot not found')

    current_week_id = current_snapshot.get('week_id')
    snapshots = (
        list_snapshots_before(chart_history_table, current_week_id, history_limit)
        if current_week_id
        else list_snapshots(chart_history_table, history_limit)
    )
    return build_chart_brief(current_snapshot, snapshots)


def list_campaigns(campaigns_table, limit=20, next_token=None):
    query_args = {
        'KeyConditionExpression': Key('pk').eq('CAMPAIGN'),
        'ScanIndexForward': False,
        'Limit': limit
    }
    if next_token:
        query_args['ExclusiveStartKey'] = decode_page_token(next_token)

    response = campaigns_table.query(**query_args)
    items = [campaign_index_item(item) for item in response.get('Items', [])]
    token = encode_page_token(response['LastEvaluatedKey']) if response.get('LastEvaluatedKey') else None
    return {
        'campaigns': items,
        'count': len(items),
        'limit': limit,
        'next_token': token
    }


def get_campaign(campaigns_table, week_id):
    response = campaigns_table.get_item(
        Key={
            'pk': 'CAMPAIGN',
            'sk': f'WEEK#{week_id}'
        }
    )
    return response.get('Item')


def list_campaign_revisions(campaigns_table, week_id, limit=50):
    response = campaigns_table.query(
        KeyConditionExpression=(
            Key('pk').eq('CAMPAIGN_REVISION') &
            Key('sk').begins_with(f'WEEK#{week_id}#REV#')
        ),
        ScanIndexForward=False,
        Limit=limit
    )
    return [campaign_revision_index_item(item) for item in response.get('Items', [])]


def get_campaign_revision(campaigns_table, week_id, revision_id):
    response = campaigns_table.get_item(
        Key={
            'pk': 'CAMPAIGN_REVISION',
            'sk': f'WEEK#{week_id}#REV#{revision_id}'
        }
    )
    return response.get('Item')


def list_campaign_feedback(campaigns_table, week_id, revision_id, limit=50):
    response = campaigns_table.query(
        KeyConditionExpression=(
            Key('pk').eq('CAMPAIGN_FEEDBACK') &
            Key('sk').begins_with(f'WEEK#{week_id}#REV#{revision_id}#')
        ),
        ScanIndexForward=False,
        Limit=limit
    )
    return response.get('Items', [])


def list_all_campaign_feedback_for_week(campaigns_table, week_id, limit=500):
    response = campaigns_table.query(
        KeyConditionExpression=(
            Key('pk').eq('CAMPAIGN_FEEDBACK') &
            Key('sk').begins_with(f'WEEK#{week_id}#')
        ),
        ScanIndexForward=False,
        Limit=limit
    )
    return response.get('Items', [])


def list_all_campaign_feedback(campaigns_table, limit=500):
    limit = min(int(limit or 500), 1000)
    items = []
    query_args = {
        'IndexName': 'gsi1',
        'KeyConditionExpression': Key('gsi_pk').eq('FEEDBACK_SUMMARY'),
        'ScanIndexForward': False,
        'Limit': limit
    }
    while len(items) < limit:
        response = campaigns_table.query(**query_args)
        items.extend(response.get('Items', []))
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        query_args['ExclusiveStartKey'] = last_key
        query_args['Limit'] = max(1, min(1000, limit - len(items)))
    return items[:limit]


def summarize_campaign_feedback(feedback_items):
    summary = {
        'total': len(feedback_items),
        'ratings': count_feedback_group(feedback_items, lambda item: item.get('rating')),
        'asset_types': [],
        'models': [],
        'prompts': [],
        'recent_negative': []
    }
    summary['asset_types'] = summarize_feedback_groups(feedback_items, lambda item: item.get('asset_type'))
    summary['models'] = summarize_feedback_groups(feedback_items, lambda item: item.get('model_id') or 'unknown')
    summary['prompts'] = summarize_feedback_groups(feedback_items, prompt_group_key)
    summary['recent_negative'] = [
        feedback_summary_item(item)
        for item in sorted(feedback_items, key=lambda item: item.get('created_at') or '', reverse=True)
        if item.get('rating') == 'down'
    ][:10]
    return summary


def summarize_feedback_groups(items, key_fn):
    grouped = {}
    for item in items:
        key = key_fn(item) or 'unknown'
        grouped.setdefault(key, []).append(item)
    return [
        {
            'key': key,
            'count': len(values),
            'up': len([item for item in values if item.get('rating') == 'up']),
            'down': len([item for item in values if item.get('rating') == 'down']),
            'down_rate': round(
                len([item for item in values if item.get('rating') == 'down']) / len(values),
                3
            ) if values else 0
        }
        for key, values in sorted(grouped.items(), key=lambda entry: (-len(entry[1]), entry[0]))
    ]


def count_feedback_group(items, key_fn):
    counts = {}
    for item in items:
        key = key_fn(item) or 'unknown'
        counts[key] = counts.get(key, 0) + 1
    return counts


def prompt_group_key(item):
    prompt_refs = item.get('prompt_refs') if isinstance(item.get('prompt_refs'), dict) else {}
    if not prompt_refs:
        return 'built-in-or-unknown'
    parts = []
    for section, ref in sorted(prompt_refs.items()):
        ref = ref if isinstance(ref, dict) else {}
        source = ref.get('source') or 'unknown'
        identifier = ref.get('prompt_identifier') or ref.get('prompt_arn') or source
        version = ref.get('prompt_version') or '?'
        parts.append(f'{section}:{identifier}@{version}')
    return ', '.join(parts)


def feedback_summary_item(item):
    return {
        'week_id': item.get('week_id'),
        'revision_id': item.get('revision_id'),
        'asset_type': item.get('asset_type'),
        'rating': item.get('rating'),
        'feedback_text': item.get('feedback_text'),
        'model_id': item.get('model_id'),
        'created_at': item.get('created_at'),
        'created_by': item.get('created_by')
    }


def put_campaign_feedback(campaigns_table, feedback):
    feedback = normalize_campaign_feedback(feedback)
    campaigns_table.put_item(Item=feedback)
    return feedback


def normalize_campaign_feedback(feedback):
    feedback = feedback if isinstance(feedback, dict) else {}
    week_id = str(feedback.get('week_id') or '').strip()
    revision_id = str(feedback.get('revision_id') or '').strip()
    asset_type = str(feedback.get('asset_type') or '').strip()
    rating = str(feedback.get('rating') or '').strip().lower()
    created_at = str(feedback.get('created_at') or utc_now_iso()).strip()

    if not valid_week_id(week_id):
        raise ValueError('week_id must be in YYYY-MM-DD format')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', revision_id):
        raise ValueError('revision_id is invalid')
    if asset_type not in {'infographic', 'social', 'radio'}:
        raise ValueError('asset_type must be one of: infographic, social, radio')
    if rating not in {'up', 'down'}:
        raise ValueError('rating must be one of: up, down')

    return {
        'pk': 'CAMPAIGN_FEEDBACK',
        'sk': feedback_sort_key(week_id, revision_id, asset_type, created_at),
        'gsi_pk': 'FEEDBACK_SUMMARY',
        'gsi_sk': feedback_summary_sort_key(week_id, revision_id, asset_type, created_at),
        'week_id': week_id,
        'revision_id': revision_id,
        'asset_type': asset_type,
        'rating': rating,
        'feedback_text': str(feedback.get('feedback_text') or '').strip(),
        'prompt_refs': deepcopy(feedback.get('prompt_refs') or {}),
        'model_id': feedback.get('model_id'),
        'created_at': created_at,
        'created_by': feedback.get('created_by')
    }


def feedback_sort_key(week_id, revision_id, asset_type, created_at):
    safe_created_at = re.sub(r'[^0-9A-Za-z]', '', str(created_at))[:32]
    return f'WEEK#{week_id}#REV#{revision_id}#ASSET#{asset_type}#TS#{safe_created_at}'


def feedback_summary_sort_key(week_id, revision_id, asset_type, created_at):
    safe_created_at = re.sub(r'[^0-9A-Za-z]', '', str(created_at))[:32]
    return f'TS#{safe_created_at}#WEEK#{week_id}#REV#{revision_id}#ASSET#{asset_type}'


def put_campaign(campaigns_table, campaign):
    campaigns_table.put_item(Item=campaign)
    return campaign


def put_campaign_with_revision(campaigns_table, campaign, parent_revision_id=None):
    campaign.pop('failure', None)
    revision = create_campaign_revision(campaign, parent_revision_id)
    campaign['active_revision_id'] = revision['revision_id']
    campaign['active_revision_key'] = {
        'pk': revision['pk'],
        'sk': revision['sk']
    }
    campaign['revision_count'] = int(campaign.get('revision_count') or campaign.get('regeneration_count') or 0) + 1
    if campaign.get('status') == 'approved':
        campaign['approved_revision_id'] = revision['revision_id']

    campaigns_table.put_item(Item=campaign)
    campaigns_table.put_item(Item=revision)
    return campaign


def create_campaign_revision(campaign, parent_revision_id=None):
    week_id = campaign.get('week_id')
    revision_id = campaign_revision_id(campaign)
    return {
        'pk': 'CAMPAIGN_REVISION',
        'sk': f'WEEK#{week_id}#REV#{revision_id}',
        'week_id': week_id,
        'revision_id': revision_id,
        'parent_revision_id': parent_revision_id,
        'status': campaign.get('status', 'draft'),
        'source_snapshot_key': campaign.get('source_snapshot_key'),
        'generated_at': campaign.get('generated_at'),
        'generated_by': campaign.get('generated_by'),
        'requested_by': campaign.get('requested_by'),
        'generator': deepcopy(campaign.get('generator') or {}),
        'chart_brief': deepcopy(campaign.get('chart_brief') or {}),
        'radio_reads': deepcopy(campaign.get('radio_reads') or {}),
        'infographic': deepcopy(campaign.get('infographic') or {}),
        'infographic_asset': deepcopy(campaign.get('infographic_asset') or {}),
        'infographic_asset_validation': deepcopy(campaign.get('infographic_asset_validation') or {}),
        'infographic_png': deepcopy(campaign.get('infographic_png') or {}),
        'social': deepcopy(campaign.get('social') or {}),
        'review': deepcopy(campaign.get('review') or {}),
        'created_at': utc_now_iso()
    }


def campaign_revision_id(campaign):
    raw = campaign.get('generated_at') or utc_now_iso()
    compact = re.sub(r'[^0-9A-Za-z]', '', str(raw))
    if compact:
        return compact[:32]
    return re.sub(r'[^0-9A-Za-z]', '', utc_now_iso())[:32]


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def put_campaign_progress(campaigns_table, week_id, stage, message, sections=None, requested_by=None, generated_by=None, timestamp=None):
    item = {
        'pk': 'CAMPAIGN',
        'sk': f'WEEK#{week_id}',
        'week_id': week_id,
        'status': 'processing',
        'requested_by': requested_by,
        'generated_by': generated_by or 'campaign-generator',
        'generated_at': timestamp,
        'campaign_progress': {
            'stage': stage,
            'message': message,
            'updated_at': timestamp
        }
    }
    if sections:
        item['requested_sections'] = sections

    campaigns_table.put_item(Item=item)
    return item


def update_campaign_progress(campaigns_table, week_id, stage, message, status='processing', timestamp=None, error=None):
    existing = get_campaign(campaigns_table, week_id) if status == 'failed' else None
    retained_assets = bool(existing and campaign_has_generated_assets(existing))
    effective_status = existing.get('status') if retained_assets else status
    if retained_assets and effective_status in {'failed', 'processing'}:
        effective_status = 'draft'
    if retained_assets:
        message = f'{message} Existing generated campaign assets were retained.'

    names = {
        '#status': 'status',
        '#campaign_progress': 'campaign_progress'
    }
    values = {
        ':status': effective_status,
        ':campaign_progress': {
            'stage': stage,
            'message': message,
            'updated_at': timestamp
        }
    }
    assignments = ['#status = :status', '#campaign_progress = :campaign_progress']
    if error:
        names['#failure'] = 'failure'
        values[':failure'] = {
            'reason': stage,
            'message': message,
            'error': str(error)
        }
        assignments.append('#failure = :failure')

    response = campaigns_table.update_item(
        Key={
            'pk': 'CAMPAIGN',
            'sk': f'WEEK#{week_id}'
        },
        UpdateExpression='SET ' + ', '.join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues='ALL_NEW'
    )
    return response.get('Attributes')


def campaign_has_generated_assets(campaign):
    if not campaign:
        return False
    asset_fields = (
        'active_revision_id',
        'infographic_png',
        'infographic_asset',
        'radio_reads',
        'social'
    )
    return any(bool(campaign.get(field)) for field in asset_fields)


def update_campaign_status(campaigns_table, week_id, status, actor=None, timestamp=None):
    status_fields = {
        'reviewed': ('reviewed_by', 'reviewed_at'),
        'approved': ('approved_by', 'approved_at'),
        'published': ('published_by', 'published_at')
    }
    names = {'#status': 'status'}
    values = {':status': status}
    assignments = ['#status = :status']

    if status in status_fields:
        by_field, at_field = status_fields[status]
        names[f'#{by_field}'] = by_field
        names[f'#{at_field}'] = at_field
        values[f':{by_field}'] = actor
        values[f':{at_field}'] = timestamp
        assignments.extend([f'#{by_field} = :{by_field}', f'#{at_field} = :{at_field}'])

    response = campaigns_table.update_item(
        Key={
            'pk': 'CAMPAIGN',
            'sk': f'WEEK#{week_id}'
        },
        UpdateExpression='SET ' + ', '.join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues='ALL_NEW'
    )
    return response.get('Attributes')


def approve_campaign_revision(campaigns_table, week_id, revision_id, actor=None, timestamp=None):
    revision = get_campaign_revision(campaigns_table, week_id, revision_id)
    if not revision:
        raise ValueError('Campaign revision not found')

    campaign = get_campaign(campaigns_table, week_id) or {
        'pk': 'CAMPAIGN',
        'sk': f'WEEK#{week_id}',
        'week_id': week_id
    }
    for key in (
        'source_snapshot_key',
        'generated_at',
        'generated_by',
        'requested_by',
        'generator',
        'chart_brief',
        'radio_reads',
        'infographic',
        'infographic_asset',
        'infographic_png',
        'social',
        'review'
    ):
        if key in revision:
            campaign[key] = deepcopy(revision[key])

    campaign['status'] = 'approved'
    campaign['active_revision_id'] = revision_id
    campaign['approved_revision_id'] = revision_id
    campaign['active_revision_key'] = {
        'pk': revision['pk'],
        'sk': revision['sk']
    }
    campaign['approved_by'] = actor
    campaign['approved_at'] = timestamp

    campaigns_table.put_item(Item=campaign)
    campaigns_table.update_item(
        Key={
            'pk': revision['pk'],
            'sk': revision['sk']
        },
        UpdateExpression='SET #status = :status, #approved_by = :approved_by, #approved_at = :approved_at',
        ExpressionAttributeNames={
            '#status': 'status',
            '#approved_by': 'approved_by',
            '#approved_at': 'approved_at'
        },
        ExpressionAttributeValues={
            ':status': 'approved',
            ':approved_by': actor,
            ':approved_at': timestamp
        }
    )
    return campaign


def update_campaign_content(campaigns_table, week_id, updates, actor=None, timestamp=None):
    allowed = {
        'review'
    }
    assignments = []
    names = {}
    values = {}

    for key, value in updates.items():
        if key not in allowed:
            continue
        names[f'#{key}'] = key
        values[f':{key}'] = value
        assignments.append(f'#{key} = :{key}')

    if actor:
        names['#last_edited_by'] = 'last_edited_by'
        values[':last_edited_by'] = actor
        assignments.append('#last_edited_by = :last_edited_by')

    if timestamp:
        names['#last_edited_at'] = 'last_edited_at'
        values[':last_edited_at'] = timestamp
        assignments.append('#last_edited_at = :last_edited_at')

    if not assignments:
        raise ValueError('No editable campaign fields supplied')

    response = campaigns_table.update_item(
        Key={
            'pk': 'CAMPAIGN',
            'sk': f'WEEK#{week_id}'
        },
        UpdateExpression='SET ' + ', '.join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues='ALL_NEW'
    )
    return response.get('Attributes')


def delete_campaign(campaigns_table, week_id):
    response = campaigns_table.delete_item(
        Key={
            'pk': 'CAMPAIGN',
            'sk': f'WEEK#{week_id}'
        },
        ReturnValues='ALL_OLD'
    )
    return response.get('Attributes')


def delete_campaign_records(campaigns_table, week_id):
    campaign = delete_campaign(campaigns_table, week_id)
    revisions = raw_campaign_revisions(campaigns_table, week_id)
    feedback = list_all_campaign_feedback_for_week(campaigns_table, week_id)
    for item in revisions + feedback:
        campaigns_table.delete_item(Key={'pk': item['pk'], 'sk': item['sk']})
    return {
        'campaign': campaign,
        'revisions': revisions,
        'feedback': feedback,
        'deleted_revision_count': len(revisions),
        'deleted_feedback_count': len(feedback)
    }


def raw_campaign_revisions(campaigns_table, week_id, limit=100):
    response = campaigns_table.query(
        KeyConditionExpression=(
            Key('pk').eq('CAMPAIGN_REVISION') &
            Key('sk').begins_with(f'WEEK#{week_id}#REV#')
        ),
        ScanIndexForward=False,
        Limit=limit
    )
    return response.get('Items', [])


def campaign_index_item(campaign):
    return {
        'week_id': campaign.get('week_id'),
        'snapshot_key': campaign.get('source_snapshot_key'),
        'status': campaign.get('status'),
        'generated_at': campaign.get('generated_at'),
        'generated_by': campaign.get('generated_by'),
        'requested_by': campaign.get('requested_by'),
        'reviewed_at': campaign.get('reviewed_at'),
        'approved_at': campaign.get('approved_at'),
        'published_at': campaign.get('published_at'),
        'campaign_progress': campaign.get('campaign_progress'),
        'failure': campaign.get('failure'),
        'active_revision_id': campaign.get('active_revision_id'),
        'approved_revision_id': campaign.get('approved_revision_id'),
        'revision_count': campaign.get('revision_count'),
        'href': f"/api/campaigns/{campaign.get('week_id')}" if campaign.get('week_id') else None
    }


def campaign_revision_index_item(revision):
    infographic_asset = revision.get('infographic_asset') or {}
    metadata = infographic_asset.get('metadata') or {}
    png = revision.get('infographic_png') or {}
    return {
        'week_id': revision.get('week_id'),
        'revision_id': revision.get('revision_id'),
        'parent_revision_id': revision.get('parent_revision_id'),
        'status': revision.get('status'),
        'created_at': revision.get('created_at'),
        'generated_at': revision.get('generated_at'),
        'generated_by': revision.get('generated_by'),
        'requested_by': revision.get('requested_by'),
        'model': (revision.get('generator') or {}).get('model'),
        'template_id': metadata.get('template_id'),
        'template_version': metadata.get('template_version'),
        'has_png': bool(png.get('key')),
        'href': (
            f"/api/campaigns/{revision.get('week_id')}/revisions/{revision.get('revision_id')}"
            if revision.get('week_id') and revision.get('revision_id')
            else None
        )
    }
