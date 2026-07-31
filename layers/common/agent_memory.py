"""Optional AgentCore Memory adapter for campaign generation."""
import json
import os
from datetime import datetime, timezone


DEFAULT_NAMESPACE = '/muddys/chart-campaigns'
DEFAULT_ACTOR_ID = 'muddys-chart-agent'


def memory_enabled():
    return bool(os.environ.get('AGENTCORE_MEMORY_ID', '').strip())


def retrieve_campaign_memory(chart_brief, top_k=5):
    """Return relevant prior campaign memory records, or [] when unavailable."""
    memory_id = os.environ.get('AGENTCORE_MEMORY_ID', '').strip()
    if not memory_id:
        return []

    query = memory_search_query(chart_brief)
    try:
        client = _client()
        response = client.retrieve_memory_records(
            memoryId=memory_id,
            namespace=DEFAULT_NAMESPACE,
            searchCriteria={
                'searchQuery': query,
                'topK': top_k
            }
        )
    except Exception as e:
        print(f'AgentCore Memory retrieval failed; continuing without memory: {e}')
        return []

    records = response.get('memoryRecordSummaries') or response.get('memoryRecords') or []
    current_week_id = chart_brief.get('week_id')
    visible_records = []
    for record in records:
        simplified = _simplify_record(record)
        memory_week_id = _metadata_value(simplified.get('metadata', {}), 'week_id')
        if current_week_id and (not memory_week_id or memory_week_id >= current_week_id):
            continue
        visible_records.append(simplified)
    return visible_records


def remember_campaign(campaign):
    """Persist a generated campaign event to AgentCore Memory when configured."""
    memory_id = os.environ.get('AGENTCORE_MEMORY_ID', '').strip()
    if not memory_id:
        return None

    try:
        client = _client()
        response = client.create_event(
            memoryId=memory_id,
            actorId=DEFAULT_ACTOR_ID,
            sessionId=f"chart-campaign-{campaign.get('week_id', 'unknown')}",
            eventTimestamp=datetime.now(timezone.utc),
            payload=[
                {
                    'conversational': {
                        'content': {
                            'text': campaign_memory_text(campaign)
                        },
                        'role': 'ASSISTANT'
                    }
                }
            ],
            branch={
                'name': 'main'
            },
            metadata={
                'week_id': {
                    'stringValue': str(campaign.get('week_id', 'unknown'))
                },
                'content_type': {
                    'stringValue': 'weekly_chart_campaign'
                },
                'status': {
                    'stringValue': str(campaign.get('status', 'unknown'))
                }
            }
        )
        event = response.get('event') or {}
        return event.get('eventId') or response.get('eventId') or response.get('id')
    except Exception as e:
        print(f'AgentCore Memory write failed; campaign was still generated: {e}')
        return None


def remember_feedback(feedback):
    """Persist campaign feedback to AgentCore Memory so future generations learn from it.

    Each feedback submission (especially thumbs-down with text) becomes a memory event
    that semantic search can surface when generating future campaigns. This enables
    the system to avoid repeating mistakes and respect reviewer preferences.
    """
    memory_id = os.environ.get('AGENTCORE_MEMORY_ID', '').strip()
    if not memory_id:
        return None

    # Only write meaningful feedback to memory (thumbs-down, or thumbs-up with text)
    rating = feedback.get('rating', '')
    feedback_text = (feedback.get('feedback_text') or '').strip()
    if rating == 'up' and not feedback_text:
        # Thumbs-up without text doesn't add useful information to memory
        return None

    week_id = feedback.get('week_id', 'unknown')
    asset_type = feedback.get('asset_type', 'unknown')

    # Build a natural-language memory event that semantic search will match
    if rating == 'down':
        sentiment = 'negative'
        prefix = f"Reviewer disliked the {asset_type} content for week {week_id}."
    else:
        sentiment = 'positive'
        prefix = f"Reviewer approved the {asset_type} content for week {week_id}."

    memory_text = prefix
    if feedback_text:
        memory_text += f" Reviewer comment: {feedback_text}"

    try:
        client = _client()
        response = client.create_event(
            memoryId=memory_id,
            actorId=feedback.get('created_by') or 'reviewer',
            sessionId=f"campaign-feedback-{week_id}",
            eventTimestamp=datetime.now(timezone.utc),
            payload=[
                {
                    'conversational': {
                        'content': {
                            'text': memory_text
                        },
                        'role': 'USER'
                    }
                }
            ],
            branch={
                'name': 'main'
            },
            metadata={
                'week_id': {
                    'stringValue': str(week_id)
                },
                'content_type': {
                    'stringValue': 'campaign_feedback'
                },
                'asset_type': {
                    'stringValue': str(asset_type)
                },
                'rating': {
                    'stringValue': str(rating)
                }
            }
        )
        event = response.get('event') or {}
        event_id = event.get('eventId') or response.get('eventId') or response.get('id')
        print(f"Feedback memory event written: {event_id} ({sentiment} {asset_type} for {week_id})")
        return event_id
    except Exception as e:
        print(f'AgentCore Memory feedback write failed (non-fatal): {e}')
        return None


def memory_search_query(chart_brief):
    tracks = ', '.join(
        track.get('track', '')
        for track in chart_brief.get('tracks', [])[:10]
        if track.get('track')
    )
    return (
        f"Muddy's weekly Top 10 campaign memory for week {chart_brief.get('week_id')}. "
        f"Relevant chart tracks: {tracks}. "
        "Recall previous editorial angles, phrases to avoid repeating, recurring artist context, "
        "and reviewer preferences."
    )


def campaign_memory_text(campaign):
    chart_brief = campaign.get('chart_brief') or {}
    memory_doc = {
        'content_type': 'weekly_chart_campaign',
        'week_id': campaign.get('week_id'),
        'status': campaign.get('status'),
        'generated_at': campaign.get('generated_at'),
        'chart_story': _safe_get(campaign, ['infographic', 'chart_story']),
        'movement_summary': _safe_get(campaign, ['infographic', 'movement_summary']),
        'number_one': _safe_get(chart_brief, ['notables', 'number_one', 'track']),
        'tracks': [
            {
                'rank': track.get('rank'),
                'track': track.get('track'),
                'movement': track.get('movement'),
                'play_count': track.get('play_count')
            }
            for track in chart_brief.get('tracks', [])[:10]
        ],
        'social_teaser': _safe_get(campaign, ['social', 'teaser', 'short_copy']),
        'radio_intro': _safe_get(campaign, ['radio_reads', 'intro']),
        'generator': campaign.get('generator', {})
    }
    return json.dumps(memory_doc, sort_keys=True)


def _client():
    import boto3
    return boto3.client('bedrock-agentcore')


def _safe_get(value, path):
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _simplify_record(record):
    content = (
        record.get('content')
        or record.get('text')
        or record.get('summary')
        or record.get('memoryRecord')
        or record
    )
    if isinstance(content, dict):
        content_text = json.dumps(content, sort_keys=True)
    else:
        content_text = str(content)

    return {
        'memory_record_id': record.get('memoryRecordId') or record.get('id'),
        'content': content_text,
        'score': record.get('score'),
        'metadata': record.get('metadata') or {}
    }


def _metadata_value(metadata, key):
    value = metadata.get(key) if isinstance(metadata, dict) else None
    if isinstance(value, dict):
        for typed_key in ('stringValue', 'numberValue', 'booleanValue'):
            if typed_key in value:
                return str(value[typed_key])
    if value is None:
        return None
    return str(value)
