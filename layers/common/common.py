"""
Shared utilities for Muddy's Top 10 application
"""
import os
import json
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


def get_env(key, default=None):
    """Get environment variable"""
    return os.environ.get(key, default)


def get_timestamp():
    """Get current Unix timestamp"""
    return int(datetime.now(timezone.utc).timestamp())


def get_week_start(timestamp=None):
    """Get the start of the week (Monday 00:00) for a given timestamp"""
    if timestamp is None:
        timestamp = get_timestamp()

    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    # Go to start of day
    dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    # Go to Monday of this week
    days_since_monday = dt.weekday()
    week_start = dt.timestamp() - (days_since_monday * 86400)
    return int(week_start)


def get_chart_week_start(timestamp=None, day_of_week='monday', hour=0):
    """
    Get the start of the chart week based on configured day and hour in PST

    Args:
        timestamp: Unix timestamp (defaults to current time)
        day_of_week: Day of week to reset (monday, tuesday, wednesday, thursday, friday, saturday, sunday)
        hour: Hour of day in PST (0-23)

    Returns:
        Unix timestamp of the most recent chart reset time
    """
    if timestamp is None:
        timestamp = get_timestamp()

    pst = ZoneInfo('America/Los_Angeles')
    dt = datetime.fromtimestamp(timestamp, tz=pst)

    # Map day names to weekday numbers (0=Monday, 6=Sunday)
    day_map = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }

    target_weekday = day_map.get(day_of_week.lower(), 0)
    current_weekday = dt.weekday()

    # Calculate days to go back to reach target weekday
    days_back = (current_weekday - target_weekday) % 7

    # Go to target day and set time
    reset_dt = dt - timedelta(days=days_back)
    reset_dt = reset_dt.replace(hour=hour, minute=0, second=0, microsecond=0)

    # If the reset time is in the future, go back one week
    if reset_dt.timestamp() > timestamp:
        reset_dt = reset_dt - timedelta(days=7)

    return int(reset_dt.timestamp())


def chart_event_timestamp_for_week(week_start_timestamp, day_of_week='monday', hour=0):
    """
    Get the first configured local chart event after a chart week starts.

    This is used for events such as campaign generation/freeze start. If the
    configured event time is before the reset time on the same local day, it is
    treated as belonging to the end of that chart week.
    """
    chart_tz = ZoneInfo('America/Los_Angeles')
    week_start = datetime.fromtimestamp(week_start_timestamp, tz=chart_tz)
    day_map = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }
    target_weekday = day_map.get(str(day_of_week).lower(), 0)
    days_ahead = (target_weekday - week_start.weekday()) % 7
    event_dt = week_start + timedelta(days=days_ahead)
    event_dt = event_dt.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    if event_dt.timestamp() <= week_start_timestamp:
        event_dt = event_dt + timedelta(days=7)
    return int(event_dt.timestamp())


def get_chart_counting_window(timestamp=None, config=None):
    """
    Return countable chart windows using reset and campaign/freeze config.

    Raw plays are still stored, but Top 10 aggregation counts only from reset to
    campaign generation when freeze is enabled.
    """
    config = config if isinstance(config, dict) else {}
    reset_day = str(config.get('day') or config.get('reset_day') or 'monday').lower()
    reset_hour = int(config.get('hour') if config.get('hour') is not None else config.get('reset_hour', 0))
    campaign_day = str(config.get('campaign_day') or reset_day).lower()
    campaign_hour = int(config.get('campaign_hour') if config.get('campaign_hour') is not None else reset_hour)
    freeze_enabled = config.get('freeze_enabled', True)
    if isinstance(freeze_enabled, str):
        freeze_enabled = freeze_enabled.lower() in ('1', 'true', 'yes', 'y', 'enabled')
    else:
        freeze_enabled = freeze_enabled is not False

    current_time = int(timestamp or get_timestamp())
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
        'freeze_start_timestamp': week_count_end if freeze_enabled else None,
        'freeze_end_timestamp': week_reset_end if freeze_enabled else None,
        'is_freeze_window': freeze_enabled and week_count_end <= current_time < week_reset_end
    }


def get_hour_block(timestamp):
    """Get the 2-hour block for a timestamp (even hours in PST)"""
    pst = ZoneInfo('America/Los_Angeles')
    dt = datetime.fromtimestamp(timestamp, tz=pst)
    hour = dt.hour
    # Round down to nearest even hour
    block_hour = (hour // 2) * 2
    block_dt = dt.replace(hour=block_hour, minute=0, second=0, microsecond=0)
    return int(block_dt.timestamp())


def format_timestamp(timestamp):
    """Format timestamp as ISO 8601 string in PST"""
    pst = ZoneInfo('America/Los_Angeles')
    return datetime.fromtimestamp(timestamp, tz=pst).isoformat()


def format_block_label(timestamp):
    """Format block timestamp as readable string in PST"""
    pst = ZoneInfo('America/Los_Angeles')
    dt = datetime.fromtimestamp(timestamp, tz=pst)
    return dt.strftime('%Y-%m-%d %I:%M %p PST')


def cors_headers():
    """Return CORS headers for API responses"""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,OPTIONS'
    }


def api_response(status_code, body):
    """Create API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': cors_headers(),
        'body': json.dumps(body, cls=DecimalEncoder)
    }


def clean_track_title(track):
    """Clean track title according to CLEAN_TITLES.MD specification"""
    import re

    if not track or ' - ' not in track:
        return track

    # Split into artist and song
    parts = track.split(' - ', 1)
    if len(parts) != 2:
        return track

    artist, song = parts
    artist = artist.strip()
    song = song.strip()

    # Promotional Entry Bypass - pass through without cleaning
    bypass_patterns = [
        r'^Muddy\'?s',  # Muddy's or Muddys
        r'^MUDDY',
        r'^Send your',
        r'^https?://',
        r'secondlife:///'
    ]

    for pattern in bypass_patterns:
        if re.search(pattern, artist, re.IGNORECASE) or re.search(pattern, song, re.IGNORECASE):
            return track

    # Clean Artist Name
    # Remove leading track numbers
    artist = re.sub(r'^\d+\.\s+', '', artist)

    # Normalize featuring credits to "ft."
    artist = re.sub(r'\b(feat\.|feat|featuring|ft\.|ft|Feat\.|Feat|Featuring|FT\.|FT)\b', 'ft.', artist, flags=re.IGNORECASE)

    # Normalize "n" to "&"
    artist = re.sub(r'\s+n\s+', ' & ', artist, flags=re.IGNORECASE)

    # Clean Song Name
    # Remove pool/source tags
    pool_tags = [
        r'\[Xtendz\]', r'\[Single\]', r'\[Club\]', r'\[DMS\]',
        r'\[Funkymix\]', r'\[BlenX\]', r'\[Ultimix\]', r'\[DJ Re-Grid\]'
    ]
    for tag in pool_tags:
        song = re.sub(tag, '', song, flags=re.IGNORECASE)

    # Remove quality/format suffixes
    quality_markers = [
        r'\s*-\s*HD\s*-\s*Clean$', r'\s*-\s*HD\s*-\s*Dirty$',
        r'\s*-\s*qHD\s*-\s*Clean$', r'\s*-\s*qHD\s*-\s*Dirty$',
        r'\s*-\s*1080\s*-\s*Clean$', r'\s*-\s*1080\s*-\s*Dirty$',
        r'\s*-\s*Clean$', r'\s*-\s*Dirty$', r'\s*-\s*HD$', r'\s*-\s*qHD$', r'\s*-\s*1080$',
        r'\s*\(Clean\)$', r'\s*\(Dirty\)$',
        r'\s*\(Explicit Edit\)$', r'\s*\(Explicit Version\)$'
    ]
    for marker in quality_markers:
        song = re.sub(marker, '', song, flags=re.IGNORECASE)

    # Remove DJ/Radio markers
    song = re.sub(r'\s*\(Lyric Video\)$', '', song, flags=re.IGNORECASE)
    song = re.sub(r'\s*\(Radio\)\s*\d*$', '', song, flags=re.IGNORECASE)
    song = re.sub(r'\s*\(DJ Beats\)(\s*\(\d+\))?$', '', song, flags=re.IGNORECASE)

    # Remove BPM transition markers
    song = re.sub(r'\s*\[\d+-\d+\]$', '', song)
    song = re.sub(r'\s*\(Transition\s+\d+-\d+\)$', '', song, flags=re.IGNORECASE)
    song = re.sub(r'\s*\(\d+~\d+\)$', '', song)
    song = re.sub(r'\s*\(\d+\)$', '', song)  # Trailing BPM numbers

    # Remove trailing BPM numbers (typically 100-200 range)
    # Don't remove small numbers that might be part of the title (e.g., "12 to 12")
    song = re.sub(r'\s+(1[0-9]{2}|200)$', '', song)  # Matches 100-199, 200

    # Remove remix/version information in parentheses at end
    remix_words = r'(remix|mix|edit|version|bootleg|mashup|remaster)'
    song = re.sub(rf'\s*\([^)]*{remix_words}[^)]*\)$', '', song, flags=re.IGNORECASE)

    # Remove trailing bracket content (unless it contains URLs)
    if not re.search(r'https?://', song):
        song = re.sub(r'\s*\[[^\]]+\]$', '', song)

    # Collapse multiple spaces and trim
    artist = re.sub(r'\s+', ' ', artist).strip()
    song = re.sub(r'\s+', ' ', song).strip()

    return f"{artist} - {song}"
