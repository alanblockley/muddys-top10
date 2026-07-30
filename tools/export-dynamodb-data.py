#!/usr/bin/env python3
"""
Export all application DynamoDB tables for a CloudFormation stack.

Usage:
    python3 tools/export-dynamodb-data.py STACK_NAME

Requires AWS CLI v2 on PATH. The output file is ready for
tools/import-dynamodb-data.py.
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


TABLE_OUTPUTS = {
    "tracks": "TracksTableName",
    "config": "ConfigTableName",
    "chart_history": "ChartHistoryTableName",
    "chart_campaigns": "ChartCampaignsTableName",
}
REQUIRED_TABLES = {"tracks", "config"}


def run_aws(args):
    command = ["aws", *args]
    result = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n{result.stderr.strip()}"
        )
    return result.stdout


def stack_outputs(stack_name, region):
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
    return {
        output["OutputKey"]: output["OutputValue"]
        for output in outputs
    }


def resolve_tables(stack_name, region):
    outputs = stack_outputs(stack_name, region)
    tables = {}
    missing_required = []

    for logical_name, output_key in TABLE_OUTPUTS.items():
        table_name = outputs.get(output_key)
        if table_name:
            tables[logical_name] = table_name
        elif logical_name in REQUIRED_TABLES:
            missing_required.append(output_key)
        else:
            print(f"Skipping optional table {logical_name}: stack output {output_key} not found")

    if missing_required:
        joined = ", ".join(missing_required)
        raise RuntimeError(f"Stack is missing required DynamoDB outputs: {joined}")

    return tables


def scan_table(table_name, region):
    items = []
    exclusive_start_key = None

    while True:
        args = [
            "dynamodb",
            "scan",
            "--table-name",
            table_name,
            "--output",
            "json",
        ]
        if region:
            args.extend(["--region", region])
        if exclusive_start_key:
            args.extend(["--exclusive-start-key", json.dumps(exclusive_start_key)])

        response = json.loads(run_aws(args))
        items.extend(response.get("Items", []))

        exclusive_start_key = response.get("LastEvaluatedKey")
        if not exclusive_start_key:
            break

    return items


def default_output_path(stack_name):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_stack = "".join(
        char if char.isalnum() or char in ("-", "_") else "_"
        for char in stack_name
    )
    return Path(f"dynamodb-export-{safe_stack}-{timestamp}.json")


def export_data(stack_name, output_path, region):
    tables = resolve_tables(stack_name, region)

    export = {
        "format": "muddys-top10-dynamodb-export-v1",
        "source_stack": stack_name,
        "source_region": region or "aws-cli-default",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
    }

    for logical_name, table_name in tables.items():
        print(f"Scanning {logical_name}: {table_name}")
        items = scan_table(table_name, region)
        export["tables"][logical_name] = {
            "source_table": table_name,
            "output_key": TABLE_OUTPUTS[logical_name],
            "item_count": len(items),
            "items": items,
        }
        print(f"  exported {len(items)} item(s)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(export, indent=2) + "\n", encoding="utf-8")
    print(f"Export written to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export all DynamoDB data for a deployed stack."
    )
    parser.add_argument("stack_name", help="CloudFormation stack name to export from")
    parser.add_argument(
        "--output",
        help="Output JSON file. Defaults to dynamodb-export-STACK-TIMESTAMP.json",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region. Defaults to current AWS CLI config/session region.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    output_path = Path(args.output) if args.output else default_output_path(args.stack_name)
    export_data(args.stack_name, output_path, args.region)


if __name__ == "__main__":
    main()
