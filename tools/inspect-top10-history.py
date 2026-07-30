#!/usr/bin/env python3
"""Inspect Top 10 history weeks and track appearances."""
import argparse
import json
import re
from collections import Counter

from top10_ops import (
    DecimalEncoder,
    decimal_to_builtin,
    get_tracks_between,
    query_items,
    resolve_tables,
)


def load_history(chart_history_table, region=None, limit=None):
    items = query_items(
        chart_history_table,
        "pk = :pk",
        {":pk": "TOP10_HISTORY"},
        region=region,
        scan_forward=True,
    )
    items.sort(key=lambda item: item.get("week_id") or item.get("sk") or "")
    if limit:
        items = items[-limit:]
    return items


def track_matches(track_name, pattern):
    if not pattern:
        return True
    try:
        return re.search(pattern, track_name, re.IGNORECASE) is not None
    except re.error:
        return pattern.lower() in track_name.lower()


def inspect(stack_name, region=None, track_pattern=None, limit=None, json_output=False, include_raw=False):
    tables = resolve_tables(
        stack_name,
        region,
        required={"tracks", "chart_history"},
    )
    weeks = load_history(tables["chart_history"], region=region, limit=limit)
    appearances = []

    for week in weeks:
        for entry in week.get("top10", []):
            track = entry.get("track", "")
            if track_matches(track, track_pattern):
                appearances.append({
                    "week_id": week.get("week_id"),
                    "week_start": week.get("week_start"),
                    "week_end": week.get("week_end"),
                    "week_start_timestamp": week.get("week_start_timestamp"),
                    "week_end_timestamp": week.get("week_end_timestamp"),
                    "rank": entry.get("rank"),
                    "track": track,
                    "play_count": entry.get("play_count"),
                    "previous_rank": entry.get("previous_rank"),
                    "movement": entry.get("movement"),
                    "movement_delta": entry.get("movement_delta"),
                })

    raw_counts = []
    if include_raw and track_pattern:
        for week in weeks:
            start_ts = week.get("week_start_timestamp")
            end_ts = week.get("week_end_timestamp")
            if start_ts is None or end_ts is None:
                continue
            tracks = get_tracks_between(tables["tracks"], int(start_ts), int(end_ts), region=region)
            matching = [track for track in tracks if track_matches(track, track_pattern)]
            counts = Counter(matching)
            raw_counts.append({
                "week_id": week.get("week_id"),
                "week_start": week.get("week_start"),
                "week_end": week.get("week_end"),
                "matching_plays": sum(counts.values()),
                "matching_variants": [
                    {
                        "track": track,
                        "plays": plays,
                    }
                    for track, plays in counts.most_common()
                ],
            })

    summary = {
        "stack": stack_name,
        "region": region or "aws-cli-default",
        "chart_history_table": tables["chart_history"],
        "tracks_table": tables["tracks"],
        "weeks_available": len(weeks),
        "first_week": weeks[0].get("week_id") if weeks else None,
        "last_week": weeks[-1].get("week_id") if weeks else None,
        "track_pattern": track_pattern,
        "matched_chart_appearances": len(appearances),
        "matched_weeks": sorted({item["week_id"] for item in appearances if item.get("week_id")}),
        "appearances": appearances,
        "raw_counts": raw_counts,
    }

    if json_output:
        print(json.dumps(decimal_to_builtin(summary), indent=2, cls=DecimalEncoder))
        return

    print(f"Stack: {stack_name} ({region or 'aws-cli-default'})")
    print(f"Chart history table: {tables['chart_history']}")
    print(f"Tracks table: {tables['tracks']}")
    print(f"Weeks available: {len(weeks)}")
    if weeks:
        print(f"Range: {weeks[0].get('week_id')} -> {weeks[-1].get('week_id')}")
        print()
        print("Persisted weeks:")
        for week in weeks:
            top10 = week.get("top10", [])
            summary = week.get("summary", {})
            print(
                f"  {week.get('week_id')}: "
                f"{week.get('week_start')} -> {week.get('week_end')} | "
                f"top10={len(top10)} total_plays={summary.get('total_plays', '-')} "
                f"unique={summary.get('unique_tracks', '-')}"
            )

    if track_pattern:
        print()
        print(f"Chart appearances matching `{track_pattern}`: {len(appearances)}")
        for item in appearances:
            print(
                f"  {item['week_id']} rank #{item['rank']} | "
                f"{item['track']} | plays={item['play_count']} "
                f"prev={item.get('previous_rank') or '-'} "
                f"move={item.get('movement') or '-'} "
                f"delta={item.get('movement_delta') if item.get('movement_delta') is not None else '-'}"
            )

        if include_raw:
            print()
            print("Raw/canonical matching plays by persisted week:")
            for item in raw_counts:
                print(
                    f"  {item['week_id']}: {item['matching_plays']} play(s) "
                    f"{item['week_start']} -> {item['week_end']}"
                )
                for variant in item["matching_variants"]:
                    print(f"    {variant['plays']}x {variant['track']}")

        print()
        print("Interpretation:")
        print("- `weeks_on_chart` is derived from persisted Top 10 appearances up to the campaign week.")
        print("- If this count is high, inspect the matched weeks above for repeated chart appearances.")
        print("- If raw variants look wrong, the issue may be title normalization/canonical_track, not campaign generation.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Summarize persisted Top 10 history and explain track appearances."
    )
    parser.add_argument("stack_name", help="CloudFormation stack name, e.g. teleport-dev-muddys-top-10")
    parser.add_argument("--region", default=None, help="AWS region. Defaults to AWS CLI config.")
    parser.add_argument("--track", help="Track substring or regex to inspect.")
    parser.add_argument("--limit", type=int, help="Limit to the latest N persisted weeks.")
    parser.add_argument("--raw", action="store_true", help="Also query raw/canonical track plays for matching track.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main():
    args = parse_args()
    inspect(
        args.stack_name,
        region=args.region,
        track_pattern=args.track,
        limit=args.limit,
        json_output=args.json,
        include_raw=args.raw,
    )


if __name__ == "__main__":
    main()
