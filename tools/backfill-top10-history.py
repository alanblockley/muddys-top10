#!/usr/bin/env python3
"""Backfill persisted weekly Top 10 history snapshots from raw track data."""
import argparse
from datetime import datetime, timezone

from top10_ops import (
    build_top10_snapshot,
    get_chart_config,
    get_chart_week_start,
    put_item,
    resolve_tables,
)


def backfill(stack_name, weeks, region=None, dry_run=True, include_current=False):
    tables = resolve_tables(
        stack_name,
        region,
        required={"tracks", "config", "chart_history"},
    )
    chart_config = get_chart_config(tables["config"], region)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    current_week_start = get_chart_week_start(
        now_ts,
        chart_config["day"],
        chart_config["hour"],
    )
    first_offset = 0 if include_current else 1
    offsets = range(first_offset, first_offset + weeks)

    print(f"Stack: {stack_name} ({region or 'aws-cli-default'})")
    print(f"Tracks table: {tables['tracks']}")
    print(f"Chart history table: {tables['chart_history']}")
    print(f"Chart reset: {chart_config['day']} {chart_config['hour']:02d}:00 SLT")
    print(f"Mode: {'dry-run' if dry_run else 'write'}")
    print()

    snapshots = []
    for offset in offsets:
        week_start = current_week_start - (offset * 7 * 86400)
        snapshot = build_top10_snapshot(
            tables["tracks"],
            tables["config"],
            week_start,
            region=region,
            generated_at_ts=now_ts,
            snapshot_type="weekly_top10",
        )
        snapshots.append(snapshot)

        print(
            f"{snapshot['week_id']}: "
            f"{len(snapshot['top10'])} track(s), "
            f"{snapshot['summary']['total_plays']} play(s), "
            f"{snapshot['summary']['unique_tracks']} unique"
        )
        if not dry_run:
            put_item(tables["chart_history"], snapshot, region)

    print()
    if dry_run:
        print(f"Dry run complete. Would write {len(snapshots)} snapshot(s). Rerun with --write to persist.")
    else:
        print(f"Backfill complete. Wrote {len(snapshots)} snapshot(s).")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate weekly top10_history snapshots for recent completed weeks."
    )
    parser.add_argument("stack_name", help="CloudFormation stack name, e.g. teleport-prod-muddys-top-10")
    parser.add_argument("--weeks", type=int, default=12, help="Number of weeks to backfill. Default: 12")
    parser.add_argument("--region", default=None, help="AWS region. Defaults to AWS CLI config.")
    parser.add_argument("--write", action="store_true", help="Persist snapshots. Default is dry-run.")
    parser.add_argument(
        "--include-current",
        action="store_true",
        help="Also include the current unfinished chart week. Normally leave this off.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.weeks < 1:
        raise SystemExit("--weeks must be at least 1")
    backfill(
        args.stack_name,
        args.weeks,
        region=args.region,
        dry_run=not args.write,
        include_current=args.include_current,
    )


if __name__ == "__main__":
    main()
