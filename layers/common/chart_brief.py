"""
Deterministic chart brief generation for agentic campaign workflows.

The brief is the factual contract consumed by editorial generators. It should
be built from persisted Top 10 history snapshots, not inferred by a model.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import re


def chart_week_id_from_timestamp(timestamp):
    chart_tz = ZoneInfo('America/Los_Angeles')
    return datetime.fromtimestamp(int(timestamp), tz=chart_tz).strftime('%Y-%m-%d')


def snapshot_week_id(snapshot):
    if snapshot.get('week_id'):
        return snapshot['week_id']
    sk = snapshot.get('sk') or snapshot.get('snapshot_key')
    if isinstance(sk, str) and sk.startswith('WEEK#'):
        return sk[5:]
    if snapshot.get('week_start_timestamp') is not None:
        return chart_week_id_from_timestamp(snapshot['week_start_timestamp'])
    return None


def split_track_name(track_name):
    if not track_name:
        return '', ''
    track_name = strip_rank_prefix(track_name)
    if ' - ' not in track_name:
        return '', track_name
    artist, title = track_name.split(' - ', 1)
    return artist.strip(), title.strip()


def strip_rank_prefix(value):
    return re.sub(r'^\s*#?\d{1,2}\s*[.)\-:]\s*', '', str(value or '')).strip()


def normalize_track_entry(entry):
    track_name = strip_rank_prefix(entry.get('track') or entry.get('canonical_track') or '')
    artist = entry.get('artist')
    title = entry.get('title')
    if not artist or not title:
        parsed_artist, parsed_title = split_track_name(track_name)
        artist = artist or parsed_artist
        title = title or parsed_title

    return {
        'rank': int(entry.get('rank')),
        'track': track_name,
        'artist': artist,
        'title': title,
        'play_count': int(entry.get('play_count', entry.get('plays', 0))),
        'previous_rank': int(entry['previous_rank']) if entry.get('previous_rank') is not None else None,
        'movement': entry.get('movement') or 'new',
        'movement_delta': int(entry['movement_delta']) if entry.get('movement_delta') is not None else None
    }


def public_snapshot(snapshot):
    week_id = snapshot_week_id(snapshot)
    return {
        'snapshot_key': snapshot.get('sk') or snapshot.get('snapshot_key'),
        'week_id': week_id,
        'snapshot_type': snapshot.get('snapshot_type', 'weekly_top10'),
        'week_start_timestamp': snapshot.get('week_start_timestamp'),
        'week_end_timestamp': snapshot.get('week_end_timestamp'),
        'previous_week_start_timestamp': snapshot.get('previous_week_start_timestamp'),
        'generated_at_timestamp': snapshot.get('generated_at_timestamp'),
        'chart_config': snapshot.get('chart_config', {}),
        'filter_patterns': snapshot.get('filter_patterns', []),
        'top10': [normalize_track_entry(track) for track in snapshot.get('top10', [])],
        'summary': snapshot.get('summary', {}),
        'chart_date': snapshot.get('chart_date'),
        'week_start': snapshot.get('week_start'),
        'week_end': snapshot.get('week_end'),
        'previous_week_start': snapshot.get('previous_week_start'),
        'previous_week_end': snapshot.get('previous_week_end')
    }


def history_index_item(snapshot):
    public = public_snapshot(snapshot)
    summary = public.get('summary', {})
    week_id = public.get('week_id')
    return {
        'week_id': week_id,
        'snapshot_key': public.get('snapshot_key'),
        'week_start': public.get('week_start'),
        'week_end': public.get('week_end'),
        'generated_at_timestamp': public.get('generated_at_timestamp'),
        'top10_count': len(public.get('top10', [])),
        'total_plays': summary.get('total_plays'),
        'unique_tracks': summary.get('unique_tracks'),
        'href': f'/api/top10/history/{week_id}' if week_id else None
    }


def build_chart_brief(current_snapshot, history_snapshots=None):
    """Build a model-safe factual brief from one current snapshot plus history."""
    current = public_snapshot(current_snapshot)
    history = [public_snapshot(item) for item in (history_snapshots or [])]
    current_week_id = current.get('week_id')

    snapshots = {
        item['week_id']: item
        for item in history + [current]
        if item.get('week_id')
    }
    ordered_weeks = sorted(snapshots.keys())
    prior_weeks = [week for week in ordered_weeks if week < current_week_id]
    visible_weeks = [week for week in ordered_weeks if week <= current_week_id]

    track_history = {}
    for week in visible_weeks:
        for track in snapshots[week].get('top10', []):
            name = track['track']
            track_history.setdefault(name, []).append({
                'week_id': week,
                'rank': track['rank'],
                'play_count': track['play_count']
            })

    tracks = []
    for track in current.get('top10', []):
        appearances = track_history.get(track['track'], [])
        prior_appearances = [item for item in appearances if item['week_id'] < current_week_id]
        best_rank = min([item['rank'] for item in appearances], default=track['rank'])
        last_seen_week = prior_appearances[-1]['week_id'] if prior_appearances else None

        enriched = dict(track)
        enriched['weeks_on_chart'] = len(appearances)
        enriched['best_rank'] = best_rank
        enriched['last_seen_week'] = last_seen_week
        tracks.append(enriched)

    notables = {
        'new_entries': [track for track in tracks if track.get('movement') == 'new'],
        'returning_tracks': [
            track for track in tracks
            if track.get('movement') == 'new' and track.get('last_seen_week')
        ],
        'biggest_climbers': sorted(
            [track for track in tracks if track.get('movement') == 'up' and track.get('movement_delta') is not None],
            key=lambda item: item['movement_delta'],
            reverse=True
        )[:3],
        'biggest_drops': sorted(
            [track for track in tracks if track.get('movement') == 'down' and track.get('movement_delta') is not None],
            key=lambda item: item['movement_delta']
        )[:3],
        'number_one': tracks[0] if tracks else None
    }

    return {
        'week_id': current_week_id,
        'source_snapshot_key': current.get('snapshot_key'),
        'chart_date': current.get('chart_date'),
        'week_start': current.get('week_start'),
        'week_end': current.get('week_end'),
        'week_start_timestamp': current.get('week_start_timestamp'),
        'week_end_timestamp': current.get('week_end_timestamp'),
        'venue_timezone': 'SLT',
        'chart_config': current.get('chart_config', {}),
        'filter_patterns': current.get('filter_patterns', []),
        'tracks': tracks,
        'notables': notables,
        'summary': {
            **current.get('summary', {}),
            'history_weeks_available': len(prior_weeks),
            'current_top10_count': len(tracks)
        }
    }
