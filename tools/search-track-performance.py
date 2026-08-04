#!/usr/bin/env python3
"""Search retained play history by artist and/or song title."""
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, time
from zoneinfo import ZoneInfo

from top10_ops import (
    DecimalEncoder,
    decimal_to_builtin,
    format_timestamp,
    get_chart_config,
    get_chart_week_start,
    query_items,
    resolve_tables,
)


CHART_TZ = ZoneInfo("America/Los_Angeles")


def compile_matcher(value, regex=False):
    if not value:
        return None
    if regex:
        pattern = re.compile(value, re.IGNORECASE)
        return lambda candidate: bool(candidate and pattern.search(str(candidate)))

    needle = value.lower()
    return lambda candidate: bool(candidate and needle in str(candidate).lower())


def parse_local_date(value, end_of_day=False):
    if not value:
        return None
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    local_dt = datetime.combine(parsed, time.max if end_of_day else time.min, tzinfo=CHART_TZ)
    return int(local_dt.timestamp())


def load_tracks(tracks_table, region=None, start_ts=None, end_ts=None):
    key_values = {":pk": "TRACK"}
    key_expression = "pk = :pk"
    expression_names = None

    if start_ts is not None and end_ts is not None:
        key_expression = "pk = :pk AND #timestamp BETWEEN :start AND :end"
        key_values.update({":start": int(start_ts), ":end": int(end_ts)})
        expression_names = {"#timestamp": "timestamp"}
    elif start_ts is not None:
        key_expression = "pk = :pk AND #timestamp >= :start"
        key_values[":start"] = int(start_ts)
        expression_names = {"#timestamp": "timestamp"}
    elif end_ts is not None:
        key_expression = "pk = :pk AND #timestamp <= :end"
        key_values[":end"] = int(end_ts)
        expression_names = {"#timestamp": "timestamp"}

    return query_items(
        tracks_table,
        key_expression,
        key_values,
        region=region,
        index_name="timestamp-index",
        scan_forward=True,
        expression_attribute_names=expression_names,
    )


def display_track(item):
    return item.get("canonical_track") or item.get("track") or ""


def item_matches(item, artist_matcher, title_matcher, track_matcher):
    canonical = display_track(item)
    raw = item.get("track") or ""
    artist = item.get("artist") or ""
    title = item.get("title") or ""

    if artist_matcher and not (artist_matcher(artist) or artist_matcher(canonical) or artist_matcher(raw)):
        return False

    if title_matcher and not (title_matcher(title) or title_matcher(canonical) or title_matcher(raw)):
        return False

    if track_matcher and not (track_matcher(canonical) or track_matcher(raw)):
        return False

    return True


def day_key(timestamp):
    return datetime.fromtimestamp(int(timestamp), tz=CHART_TZ).strftime("%Y-%m-%d")


def aggregate_periods(matches, chart_config):
    daily = defaultdict(list)
    weekly = defaultdict(list)

    for item in matches:
        timestamp = int(item["timestamp"])
        daily[day_key(timestamp)].append(item)
        week_start_ts = get_chart_week_start(timestamp, chart_config["day"], chart_config["hour"])
        weekly[day_key(week_start_ts)].append(item)

    return summarize_groups(daily), summarize_groups(weekly)


def summarize_groups(groups):
    rows = []
    for period, items in sorted(groups.items()):
        track_counts = Counter(display_track(item) for item in items)
        artist_counts = Counter(item.get("artist") or "(unknown)" for item in items)
        first_ts = min(int(item["timestamp"]) for item in items)
        last_ts = max(int(item["timestamp"]) for item in items)
        rows.append({
            "period": period,
            "plays": len(items),
            "unique_tracks": len(track_counts),
            "top_track": track_counts.most_common(1)[0][0] if track_counts else None,
            "top_track_plays": track_counts.most_common(1)[0][1] if track_counts else 0,
            "top_artist": artist_counts.most_common(1)[0][0] if artist_counts else None,
            "first_play": format_timestamp(first_ts),
            "last_play": format_timestamp(last_ts),
            "tracks": [
                {"track": track, "plays": plays}
                for track, plays in track_counts.most_common()
            ],
        })
    return rows


def print_table(title, rows, detail=False):
    print(title)
    if not rows:
        print("  No matches")
        return

    print("  Period       Plays  Unique  Top match")
    print("  -----------  -----  ------  ---------")
    for row in rows:
        top = row["top_track"] or "-"
        print(f"  {row['period']:<11}  {row['plays']:>5}  {row['unique_tracks']:>6}  {top}")
        if detail:
            for track in row["tracks"][:10]:
                print(f"      {track['plays']:>4}x {track['track']}")


def search_performance(args):
    if not any([args.artist, args.title, args.track]):
        raise SystemExit("Error: provide at least one of --artist, --title, or --track")

    tables = resolve_tables(args.stack_name, args.region, required={"tracks", "config"})
    chart_config = get_chart_config(tables["config"], args.region)
    start_ts = parse_local_date(args.from_date, end_of_day=False)
    end_ts = parse_local_date(args.to_date, end_of_day=True)

    artist_matcher = compile_matcher(args.artist, args.regex)
    title_matcher = compile_matcher(args.title, args.regex)
    track_matcher = compile_matcher(args.track, args.regex)

    tracks = load_tracks(tables["tracks"], args.region, start_ts, end_ts)
    matches = [
        item for item in tracks
        if item.get("timestamp") is not None
        and item_matches(item, artist_matcher, title_matcher, track_matcher)
    ]
    daily, weekly = aggregate_periods(matches, chart_config)

    summary = {
        "stack": args.stack_name,
        "region": args.region or "aws-cli-default",
        "tracks_table": tables["tracks"],
        "chart_config": chart_config,
        "filters": {
            "artist": args.artist,
            "title": args.title,
            "track": args.track,
            "regex": args.regex,
            "from": args.from_date,
            "to": args.to_date,
        },
        "total_scanned": len(tracks),
        "total_matches": len(matches),
        "daily": daily,
        "weekly": weekly,
    }

    if args.json:
        print(json.dumps(decimal_to_builtin(summary), indent=2, cls=DecimalEncoder))
        return

    print(f"Stack: {args.stack_name} ({args.region or 'aws-cli-default'})")
    print(f"Tracks table: {tables['tracks']}")
    print(f"Matched plays: {len(matches)} of {len(tracks)} scanned")
    print()
    print_table("Day by day", daily, detail=args.detail)
    print()
    print_table("Week by week", weekly, detail=args.detail)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Search all retained play history by artist and/or song title and aggregate performance."
    )
    parser.add_argument("stack_name", help="CloudFormation stack name, e.g. teleport-prod-muddys-top-10")
    parser.add_argument("--region", default=None, help="AWS region. Defaults to current AWS CLI config.")
    parser.add_argument("--artist", help="Artist substring to match.")
    parser.add_argument("--title", help="Song title substring to match.")
    parser.add_argument("--track", help="Whole display/raw track substring to match.")
    parser.add_argument("--regex", action="store_true", help="Treat search values as case-insensitive regexes.")
    parser.add_argument("--from", dest="from_date", help="Start date in YYYY-MM-DD, America/Los_Angeles.")
    parser.add_argument("--to", dest="to_date", help="End date in YYYY-MM-DD, America/Los_Angeles.")
    parser.add_argument("--detail", action="store_true", help="Show per-period matching track breakdown.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main():
    search_performance(parse_args())


if __name__ == "__main__":
    main()
