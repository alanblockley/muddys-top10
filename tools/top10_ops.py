"""Shared AWS CLI helpers for local Top 10 operational scripts."""
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


DAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


STACK_OUTPUTS = {
    "tracks": "TracksTableName",
    "config": "ConfigTableName",
    "chart_history": "ChartHistoryTableName",
    "chart_campaigns": "ChartCampaignsTableName",
}


class DecimalEncoder(json.JSONEncoder):
    def default(self, value):
        if isinstance(value, Decimal):
            return int(value) if value % 1 == 0 else float(value)
        return super().default(value)


def run_aws(args):
    command = ["aws", *args]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{result.stderr.strip()}")
    return result.stdout


def stack_outputs(stack_name, region=None):
    args = [
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        stack_name,
        "--query",
        "Stacks[0].Outputs",
        "--output",
        "json",
    ]
    if region:
        args.extend(["--region", region])
    outputs = json.loads(run_aws(args))
    return {item["OutputKey"]: item["OutputValue"] for item in outputs}


def resolve_tables(stack_name, region=None, required=None):
    required = set(required or STACK_OUTPUTS.keys())
    outputs = stack_outputs(stack_name, region)
    tables = {}
    missing = []
    for logical_name, output_key in STACK_OUTPUTS.items():
        table_name = outputs.get(output_key)
        if table_name:
            tables[logical_name] = table_name
        elif logical_name in required:
            missing.append(output_key)
    if missing:
        raise RuntimeError(f"Stack is missing required outputs: {', '.join(missing)}")
    return tables


def deserialize_attribute(value):
    if "S" in value:
        return value["S"]
    if "N" in value:
        raw = value["N"]
        return Decimal(raw)
    if "BOOL" in value:
        return value["BOOL"]
    if "NULL" in value:
        return None
    if "M" in value:
        return {key: deserialize_attribute(item) for key, item in value["M"].items()}
    if "L" in value:
        return [deserialize_attribute(item) for item in value["L"]]
    if "SS" in value:
        return value["SS"]
    if "NS" in value:
        return [Decimal(item) for item in value["NS"]]
    raise ValueError(f"Unsupported DynamoDB attribute value: {value}")


def deserialize_item(item):
    return {key: deserialize_attribute(value) for key, value in item.items()}


def serialize_attribute(value):
    if value is None:
        return {"NULL": True}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, int):
        return {"N": str(value)}
    if isinstance(value, Decimal):
        return {"N": str(value)}
    if isinstance(value, float):
        return {"N": str(Decimal(str(value)))}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, list):
        return {"L": [serialize_attribute(item) for item in value]}
    if isinstance(value, dict):
        return {"M": {key: serialize_attribute(item) for key, item in value.items()}}
    raise TypeError(f"Unsupported value for DynamoDB serialization: {type(value).__name__}")


def serialize_item(item):
    return {key: serialize_attribute(value) for key, value in item.items()}


def decimal_to_builtin(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, list):
        return [decimal_to_builtin(item) for item in value]
    if isinstance(value, dict):
        return {key: decimal_to_builtin(item) for key, item in value.items()}
    return value


def get_item(table_name, key, region=None):
    args = [
        "dynamodb",
        "get-item",
        "--table-name",
        table_name,
        "--key",
        json.dumps(serialize_item(key), cls=DecimalEncoder),
        "--output",
        "json",
    ]
    if region:
        args.extend(["--region", region])
    response = json.loads(run_aws(args))
    item = response.get("Item")
    return deserialize_item(item) if item else None


def put_item(table_name, item, region=None):
    path = Path("/tmp/muddys-top10-put-item.json")
    path.write_text(json.dumps(serialize_item(item), cls=DecimalEncoder), encoding="utf-8")
    args = [
        "dynamodb",
        "put-item",
        "--table-name",
        table_name,
        "--item",
        f"file://{path}",
    ]
    if region:
        args.extend(["--region", region])
    run_aws(args)


def delete_item(table_name, key, region=None):
    path = Path("/tmp/muddys-top10-delete-item.json")
    path.write_text(json.dumps(serialize_item(key), cls=DecimalEncoder), encoding="utf-8")
    args = [
        "dynamodb",
        "delete-item",
        "--table-name",
        table_name,
        "--key",
        f"file://{path}",
    ]
    if region:
        args.extend(["--region", region])
    run_aws(args)


def query_items(
    table_name,
    key_condition_expression,
    expression_attribute_values,
    region=None,
    index_name=None,
    scan_forward=True,
    expression_attribute_names=None,
):
    items = []
    exclusive_start_key = None

    while True:
        args = [
            "dynamodb",
            "query",
            "--table-name",
            table_name,
            "--key-condition-expression",
            key_condition_expression,
            "--expression-attribute-values",
            json.dumps(serialize_item(expression_attribute_values), cls=DecimalEncoder),
            "--output",
            "json",
        ]
        args.append("--scan-index-forward" if scan_forward else "--no-scan-index-forward")
        if index_name:
            args.extend(["--index-name", index_name])
        if expression_attribute_names:
            args.extend(["--expression-attribute-names", json.dumps(expression_attribute_names)])
        if region:
            args.extend(["--region", region])
        if exclusive_start_key:
            args.extend(["--exclusive-start-key", json.dumps(exclusive_start_key)])

        response = json.loads(run_aws(args))
        items.extend(deserialize_item(item) for item in response.get("Items", []))
        exclusive_start_key = response.get("LastEvaluatedKey")
        if not exclusive_start_key:
            return items


def query_items_with_limit(table_name, key_condition_expression, expression_attribute_values, region=None, limit=None, scan_forward=True):
    args = [
        "dynamodb",
        "query",
        "--table-name",
        table_name,
        "--key-condition-expression",
        key_condition_expression,
        "--expression-attribute-values",
        json.dumps(serialize_item(expression_attribute_values), cls=DecimalEncoder),
        "--output",
        "json",
    ]
    args.append("--scan-index-forward" if scan_forward else "--no-scan-index-forward")
    if limit:
        args.extend(["--limit", str(limit)])
    if region:
        args.extend(["--region", region])

    response = json.loads(run_aws(args))
    return [deserialize_item(item) for item in response.get("Items", [])]


def get_config_value(config_table, config_key, region=None):
    item = get_item(config_table, {"configKey": config_key}, region)
    return item.get("value") if item else None


def get_chart_config(config_table, region=None):
    config = get_config_value(config_table, "chart_generation", region) or {}
    valid_days = set(DAY_MAP.keys())
    reset_day = str(config.get("day", "monday")).lower()
    if reset_day not in valid_days:
        reset_day = "monday"
    reset_hour = int(config.get("hour") if config.get("hour") is not None else 0)
    campaign_day, campaign_hour = default_campaign_time(reset_day, reset_hour)
    configured_campaign_day = str(config.get("campaign_day", campaign_day)).lower()
    if configured_campaign_day not in valid_days:
        configured_campaign_day = campaign_day
    return {
        "day": reset_day,
        "hour": reset_hour,
        "campaign_generation_enabled": config.get("campaign_generation_enabled", True),
        "campaign_day": configured_campaign_day,
        "campaign_hour": int(config.get("campaign_hour") if config.get("campaign_hour") is not None else campaign_hour),
        "freeze_enabled": config.get("freeze_enabled", True),
    }


def default_campaign_time(reset_day, reset_hour):
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    campaign_hour = reset_hour - 2
    if campaign_hour >= 0:
        return reset_day, campaign_hour
    return days[(days.index(reset_day) - 1) % len(days)], campaign_hour + 24


def get_filter_patterns(config_table, region=None):
    value = get_config_value(config_table, "top10_filters", region)
    return value if isinstance(value, list) else []


def get_chart_week_start(timestamp=None, day_of_week="monday", hour=0):
    timestamp = int(timestamp or datetime.now(timezone.utc).timestamp())
    chart_tz = ZoneInfo("America/Los_Angeles")
    current = datetime.fromtimestamp(timestamp, tz=chart_tz)
    target_weekday = DAY_MAP.get(day_of_week.lower(), 0)
    days_back = (current.weekday() - target_weekday) % 7
    reset = current - timedelta(days=days_back)
    reset = reset.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    if reset.timestamp() > timestamp:
        reset = reset - timedelta(days=7)
    return int(reset.timestamp())


def chart_week_id(timestamp):
    chart_tz = ZoneInfo("America/Los_Angeles")
    return datetime.fromtimestamp(int(timestamp), tz=chart_tz).strftime("%Y-%m-%d")


def chart_event_timestamp_for_week(week_start_ts, day_of_week="monday", hour=0):
    chart_tz = ZoneInfo("America/Los_Angeles")
    week_start = datetime.fromtimestamp(int(week_start_ts), tz=chart_tz)
    target_weekday = DAY_MAP.get(day_of_week.lower(), 0)
    days_ahead = (target_weekday - week_start.weekday()) % 7
    event_dt = week_start + timedelta(days=days_ahead)
    event_dt = event_dt.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    if event_dt.timestamp() <= int(week_start_ts):
        event_dt = event_dt + timedelta(days=7)
    return int(event_dt.timestamp())


def chart_counting_window_for_week(week_start_ts, chart_config):
    week_start_ts = int(week_start_ts)
    reset_day = chart_config["day"]
    reset_hour = chart_config["hour"]
    campaign_day = chart_config.get("campaign_day", reset_day)
    campaign_hour = int(chart_config.get("campaign_hour", reset_hour))
    freeze_enabled = chart_config.get("freeze_enabled", True) is not False

    reset_end = chart_event_timestamp_for_week(week_start_ts, reset_day, reset_hour)
    count_end = (
        chart_event_timestamp_for_week(week_start_ts, campaign_day, campaign_hour)
        if freeze_enabled else reset_end
    )
    if count_end > reset_end:
        count_end = reset_end
    return count_end, reset_end


def format_timestamp(timestamp):
    chart_tz = ZoneInfo("America/Los_Angeles")
    return datetime.fromtimestamp(int(timestamp), tz=chart_tz).isoformat()


def should_filter_track(track_name, filter_patterns):
    for pattern in filter_patterns:
        try:
            if re.search(pattern, track_name, re.IGNORECASE):
                return True
        except re.error:
            if pattern.lower() in track_name.lower():
                return True
    return False


def get_tracks_between(tracks_table, start_ts, end_ts, region=None):
    items = query_items(
        tracks_table,
        "pk = :pk AND #timestamp BETWEEN :start AND :end",
        {
            ":pk": "TRACK",
            ":start": int(start_ts),
            ":end": int(end_ts),
        },
        region=region,
        index_name="timestamp-index",
        expression_attribute_names={"#timestamp": "timestamp"},
    )
    return [item.get("canonical_track") or item.get("track") for item in items if item.get("track")]


def build_top10_snapshot(tracks_table, config_table, week_start_ts, region=None, generated_at_ts=None, snapshot_type="weekly_top10"):
    chart_config = get_chart_config(config_table, region)
    filter_patterns = get_filter_patterns(config_table, region)
    week_start_ts = int(week_start_ts)
    week_end_ts, week_reset_end_ts = chart_counting_window_for_week(week_start_ts, chart_config)
    previous_week_start_ts = get_chart_week_start(week_start_ts - 1, chart_config["day"], chart_config["hour"])
    previous_week_end_ts, previous_week_reset_end_ts = chart_counting_window_for_week(previous_week_start_ts, chart_config)
    generated_at_ts = int(generated_at_ts or datetime.now(timezone.utc).timestamp())

    current_tracks = [
        track for track in get_tracks_between(tracks_table, week_start_ts, week_end_ts, region)
        if not should_filter_track(track, filter_patterns)
    ]
    previous_tracks = [
        track for track in get_tracks_between(tracks_table, previous_week_start_ts, previous_week_end_ts, region)
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
            movement = "new"
        elif previous_rank > rank:
            movement = "up"
        elif previous_rank < rank:
            movement = "down"
        else:
            movement = "same"

        top10.append({
            "rank": rank,
            "track": track,
            "play_count": int(count),
            "previous_rank": previous_rank,
            "movement": movement,
            "movement_delta": (previous_rank - rank) if previous_rank else None,
        })

    week_id = chart_week_id(week_start_ts)
    return {
        "pk": "TOP10_HISTORY",
        "sk": f"WEEK#{week_id}",
        "week_id": week_id,
        "snapshot_type": snapshot_type,
        "week_start_timestamp": week_start_ts,
        "week_end_timestamp": week_end_ts,
        "week_count_end_timestamp": week_end_ts,
        "week_reset_end_timestamp": week_reset_end_ts,
        "previous_week_start_timestamp": previous_week_start_ts,
        "previous_week_count_end_timestamp": previous_week_end_ts,
        "previous_week_reset_end_timestamp": previous_week_reset_end_ts,
        "generated_at_timestamp": generated_at_ts,
        "chart_config": chart_config,
        "filter_patterns": filter_patterns,
        "top10": top10,
        "summary": {
            "total_plays": int(sum(current_counts.values())),
            "unique_tracks": len(current_counts),
            "previous_total_plays": int(sum(previous_counts.values())),
            "previous_unique_tracks": len(previous_counts),
        },
        "chart_date": format_timestamp(week_start_ts),
        "week_start": format_timestamp(week_start_ts),
        "week_end": format_timestamp(week_end_ts),
        "week_count_end": format_timestamp(week_end_ts),
        "week_reset_end": format_timestamp(week_reset_end_ts),
        "previous_week_start": format_timestamp(previous_week_start_ts),
        "previous_week_end": format_timestamp(previous_week_end_ts),
        "previous_week_count_end": format_timestamp(previous_week_end_ts),
        "previous_week_reset_end": format_timestamp(previous_week_reset_end_ts),
        "freeze_window": {
            "enabled": chart_config.get("freeze_enabled", True),
            "start_timestamp": week_end_ts,
            "end_timestamp": week_reset_end_ts,
            "start": format_timestamp(week_end_ts),
            "end": format_timestamp(week_reset_end_ts),
            "active": False,
        },
    }
