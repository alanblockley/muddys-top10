#!/usr/bin/env python3
"""
Import a DynamoDB export into the tables for another CloudFormation stack.

Usage:
    python3 tools/import-dynamodb-data.py STACK_NAME EXPORT_FILE

Requires AWS CLI v2 on PATH. By default this overwrites items with matching
keys. Use --dry-run to inspect the target table mapping without writing.
"""

import argparse
import json
import subprocess
import tempfile
import os
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
            print(f"Skipping optional table {logical_name}: target stack output {output_key} not found")

    if missing_required:
        joined = ", ".join(missing_required)
        raise RuntimeError(f"Stack is missing required DynamoDB outputs: {joined}")

    return tables


def load_export(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "muddys-top10-dynamodb-export-v1":
        raise RuntimeError("Unsupported export format")
    return data


def chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def batch_write(table_name, items, region):
    for chunk in chunks(items, 25):
        request_items = {
            table_name: [
                {"PutRequest": {"Item": item}}
                for item in chunk
            ]
        }

        while request_items:
            request_path = None
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
                json.dump(request_items, handle)
                request_path = handle.name

            args = [
                "dynamodb",
                "batch-write-item",
                "--request-items",
                f"file://{request_path}",
                "--output",
                "json",
            ]
            if region:
                args.extend(["--region", region])

            try:
                response = json.loads(run_aws(args))
                request_items = response.get("UnprocessedItems", {})
            finally:
                if request_path:
                    os.unlink(request_path)


def import_table(table_name, serialized_items, region, dry_run):
    if dry_run:
        print(f"  dry-run: would import {len(serialized_items)} item(s)")
        return

    batch_write(table_name, serialized_items, region)
    print(f"  imported {len(serialized_items)} item(s)")


def import_data(stack_name, export_path, region, dry_run):
    export = load_export(export_path)
    target_tables = resolve_tables(stack_name, region)

    print(f"Source stack: {export.get('source_stack')} ({export.get('source_region')})")
    print(f"Target stack: {stack_name} ({region or 'aws-cli-default'})")

    for logical_name, target_table in target_tables.items():
        table_export = export.get("tables", {}).get(logical_name)
        if not table_export:
            print(f"Skipping {logical_name}: no data in export")
            continue

        items = table_export.get("items", [])
        print(f"Importing {logical_name}: {table_export.get('source_table')} -> {target_table}")
        import_table(target_table, items, region, dry_run)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import exported DynamoDB data into a deployed stack."
    )
    parser.add_argument("stack_name", help="CloudFormation stack name to import into")
    parser.add_argument("export_file", help="Export JSON file from export-dynamodb-data.py")
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region. Defaults to current AWS CLI config/session region.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show target mapping and item counts without writing data.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    import_data(args.stack_name, Path(args.export_file), args.region, args.dry_run)


if __name__ == "__main__":
    main()
