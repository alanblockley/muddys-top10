#!/usr/bin/env python3
"""Generate a test campaign from the current unfinished Top 10."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "layers", "common"))

from campaign_generation import create_campaign_draft  # noqa: E402
from chart_brief import build_chart_brief  # noqa: E402
from top10_ops import (  # noqa: E402
    DecimalEncoder,
    build_top10_snapshot,
    get_chart_config,
    get_chart_week_start,
    put_item,
    query_items_with_limit,
    resolve_tables,
)


def latest_history_snapshots(chart_history_table, current_week_id, region=None, limit=12):
    return query_items_with_limit(
        chart_history_table,
        "pk = :pk AND sk < :sk",
        {
            ":pk": "TOP10_HISTORY",
            ":sk": f"WEEK#{current_week_id}",
        },
        region=region,
        limit=limit,
        scan_forward=False,
    )


def generate_current_campaign(stack_name, region=None, sections=None, write=False):
    tables = resolve_tables(
        stack_name,
        region,
        required={"tracks", "config", "chart_history", "chart_campaigns"},
    )
    chart_config = get_chart_config(tables["config"], region)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    current_week_start = get_chart_week_start(
        now_ts,
        chart_config["day"],
        chart_config["hour"],
    )

    os.environ["CAMPAIGN_MODEL_ID"] = ""
    os.environ.setdefault("AGENTCORE_MEMORY_ID", "")

    snapshot = build_top10_snapshot(
        tables["tracks"],
        tables["config"],
        current_week_start,
        region=region,
        generated_at_ts=now_ts,
        snapshot_type="working_top10",
    )
    snapshot["sk"] = f"WORKING#{snapshot['week_id']}"
    snapshot["source_status"] = "unfinished_current_week"

    history = latest_history_snapshots(
        tables["chart_history"],
        snapshot["week_id"],
        region=region,
        limit=12,
    )
    chart_brief = build_chart_brief(snapshot, history)
    chart_brief["source_status"] = "unfinished_current_week"
    chart_brief["summary"]["campaign_test_source"] = "current_unfinished_top10"

    campaign = create_campaign_draft(
        chart_brief,
        sections=sections,
        requested_by="local-script",
        generated_by="current-top10-test",
    )
    campaign["pk"] = "CAMPAIGN_TEST"
    campaign["sk"] = f"CURRENT#{campaign['week_id']}#{now_ts}"
    campaign["status"] = "test-draft"
    campaign["test_source"] = {
        "type": "current_unfinished_top10",
        "official_history_snapshot": False,
        "tracks_table": tables["tracks"],
        "generated_at_timestamp": now_ts,
    }

    if write:
        put_item(tables["chart_campaigns"], campaign, region)

    return {
        "stack": stack_name,
        "region": region or "aws-cli-default",
        "written": write,
        "campaign_key": {
            "pk": campaign["pk"],
            "sk": campaign["sk"],
        },
        "current_snapshot": snapshot,
        "campaign": campaign,
    }


def parse_sections(value):
    if not value:
        return None
    allowed = {"radio", "infographic", "social"}
    sections = [item.strip() for item in value.split(",") if item.strip()]
    invalid = [item for item in sections if item not in allowed]
    if invalid:
        raise SystemExit(f"Invalid section(s): {', '.join(invalid)}")
    return sections


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a test campaign from the active unfinished Top 10."
    )
    parser.add_argument("stack_name", help="CloudFormation stack name, e.g. teleport-dev-muddys-top-10")
    parser.add_argument("--region", default=None, help="AWS region. Defaults to AWS CLI config.")
    parser.add_argument("--sections", help="Comma-separated sections: radio,infographic,social")
    parser.add_argument("--write", action="store_true", help="Persist under pk=CAMPAIGN_TEST. Default prints JSON only.")
    parser.add_argument("--output", help="Optional output JSON path.")
    return parser.parse_args()


def main():
    args = parse_args()
    result = generate_current_campaign(
        args.stack_name,
        region=args.region,
        sections=parse_sections(args.sections),
        write=args.write,
    )
    payload = json.dumps(result, indent=2, cls=DecimalEncoder) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload)
        print(f"Wrote test campaign JSON to {args.output}")
        if args.write:
            print(f"Persisted test campaign as {result['campaign_key']}")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
