#!/usr/bin/env python3
"""Delete campaign records and owned generated assets without touching Top 10 history."""
import argparse

from top10_ops import delete_item, query_items, resolve_tables, run_aws, stack_outputs


def campaign_records(campaigns_table, pk, region=None):
    items = query_items(
        campaigns_table,
        "pk = :pk",
        {":pk": pk},
        region=region,
        scan_forward=False,
    )
    return [
        {
            "pk": item["pk"],
            "sk": item["sk"],
            "week_id": item.get("week_id"),
            "revision_id": item.get("revision_id"),
            "asset_type": item.get("asset_type"),
            "status": item.get("status"),
            "generated_at": item.get("generated_at"),
            "generated_by": item.get("generated_by"),
            "infographic_png": item.get("infographic_png"),
        }
        for item in items
        if item.get("pk") == pk and item.get("sk")
    ]


def resolve_assets_bucket(stack_name, region=None):
    outputs = stack_outputs(stack_name, region)
    return outputs.get("CampaignAssetsBucketName")


def campaign_owned_asset_keys(records):
    keys = set()
    for record in records:
        png = record.get("infographic_png") or {}
        for field in ("key", "s3_key"):
            key = png.get(field) if isinstance(png, dict) else None
            if is_campaign_owned_asset_key(key):
                keys.add(key)
    return sorted(keys)


def is_campaign_owned_asset_key(key):
    if not key or not isinstance(key, str):
        return False
    # Do not delete global branding/template assets from this reset script.
    return key.startswith("campaigns/") or key.startswith("generated/")


def delete_s3_object(bucket, key, region=None):
    args = ["s3api", "delete-object", "--bucket", bucket, "--key", key]
    if region:
        args.extend(["--region", region])
    run_aws(args)


def clear_campaigns(stack_name, region=None, dry_run=True, include_tests=False):
    tables = resolve_tables(
        stack_name,
        region,
        required={"chart_campaigns"},
    )
    table_name = tables["chart_campaigns"]
    bucket_name = resolve_assets_bucket(stack_name, region)
    pks = ["CAMPAIGN", "CAMPAIGN_REVISION", "CAMPAIGN_FEEDBACK"]
    if include_tests:
        pks.append("CAMPAIGN_TEST")

    print(f"Stack: {stack_name} ({region or 'aws-cli-default'})")
    print(f"Campaigns table: {table_name}")
    print(f"Campaign assets bucket: {bucket_name or 'not found in stack outputs'}")
    print(f"Mode: {'dry-run' if dry_run else 'delete'}")
    print(f"Record types: {', '.join(pks)}")
    print("Top 10 history table is not touched.")
    print("Global branding/template assets are not touched.")
    print()

    records = []
    for pk in pks:
        records.extend(campaign_records(table_name, pk, region=region))

    asset_keys = campaign_owned_asset_keys(records)

    if not records and not asset_keys:
        print("No campaign records or campaign-owned assets found.")
        return

    for record in records:
        print(
            f"{record['pk']} {record['sk']} "
            f"week={record.get('week_id') or '-'} "
            f"rev={record.get('revision_id') or '-'} "
            f"asset={record.get('asset_type') or '-'} "
            f"status={record.get('status') or '-'} "
            f"generated_at={record.get('generated_at') or '-'} "
            f"generated_by={record.get('generated_by') or '-'}"
        )
        if not dry_run:
            delete_item(
                table_name,
                {
                    "pk": record["pk"],
                    "sk": record["sk"],
                },
                region=region,
            )

    if asset_keys:
        print()
        print("Campaign-owned S3 assets:")
        for key in asset_keys:
            print(f"s3://{bucket_name or '<missing-bucket-output>'}/{key}")
            if not dry_run:
                if not bucket_name:
                    raise RuntimeError("Stack is missing CampaignAssetsBucketName output; cannot delete S3 assets")
                delete_s3_object(bucket_name, key, region=region)

    print()
    if dry_run:
        print(
            f"Dry run complete. Would delete {len(records)} campaign record(s) "
            f"and {len(asset_keys)} campaign-owned S3 asset(s). Rerun with --write to delete."
        )
    else:
        print(f"Deleted {len(records)} campaign record(s) and {len(asset_keys)} campaign-owned S3 asset(s).")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Delete campaign records and owned generated assets while preserving top10_history.",
        epilog=(
            "Examples:\n"
            "  python3 tools/clear-campaigns.py teleport-dev-muddys-top-10\n"
            "  python3 tools/clear-campaigns.py teleport-dev-muddys-top-10 --write\n"
            "  python3 tools/clear-campaigns.py teleport-dev-muddys-top-10 --region us-west-2 --write"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("stack_name", help="CloudFormation stack name, e.g. teleport-dev-muddys-top-10")
    parser.add_argument("--region", default=None, help="AWS region. Defaults to AWS CLI config.")
    parser.add_argument("--write", action="store_true", help="Actually delete records. Default is dry-run.")
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Also delete CAMPAIGN_TEST records created by current-week test tooling.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    clear_campaigns(
        args.stack_name,
        region=args.region,
        dry_run=not args.write,
        include_tests=args.include_tests,
    )


if __name__ == "__main__":
    main()
