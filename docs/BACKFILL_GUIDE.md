# Backfill and Maintenance Scripts

Scripts for cleaning up and maintaining existing data in DynamoDB.

## Top 10 History Backfill

Use this when `top10_history` is missing prior weekly snapshots and you want to
generate recent AI-ready chart history from raw track plays.

Dry run the last 12 completed weeks:

```bash
python3 tools/backfill-top10-history.py teleport-prod-muddys-top-10
```

Write the snapshots:

```bash
python3 tools/backfill-top10-history.py teleport-prod-muddys-top-10 --write
```

Useful options:

- `--weeks 12`: number of completed weeks to generate.
- `--region us-west-2`: override the AWS CLI default region.
- `--include-current`: include the active unfinished week. Normally avoid this for official history.

The script resolves table names from CloudFormation outputs and writes
`TOP10_HISTORY` items into the stack's `ChartHistoryTableName`. Existing weeks
with the same `pk/sk` are replaced.

## Top 10 History Inspection

Use this when a campaign appears to show too many `weeks_on_chart`, or when you
need to understand the persisted chart date range.

Summarize persisted weeks:

```bash
python3 tools/inspect-top10-history.py teleport-dev-muddys-top-10
```

Inspect one track's chart appearances:

```bash
python3 tools/inspect-top10-history.py teleport-dev-muddys-top-10 --track "Artist - Title"
```

Also query raw/canonical plays for matching weeks:

```bash
python3 tools/inspect-top10-history.py teleport-dev-muddys-top-10 \
  --track "Artist - Title" \
  --raw
```

Useful options:

- `--limit 12`: inspect only the latest N persisted weeks.
- `--json`: output machine-readable diagnostics.
- `--region us-west-2`: override the AWS CLI default region.

## Current Unfinished Campaign Test

Use this to test campaign generation from the active, unfinished Top 10 without
publishing that chart as official history.

Print a deterministic test campaign as JSON:

```bash
python3 tools/generate-current-campaign.py teleport-dev-muddys-top-10
```

Persist the result as a test-only record:

```bash
python3 tools/generate-current-campaign.py teleport-dev-muddys-top-10 --write
```

Generate only one section:

```bash
python3 tools/generate-current-campaign.py teleport-dev-muddys-top-10 --sections radio
```

Persisted current-week test campaigns use `pk=CAMPAIGN_TEST` and an `sk` that
starts with `CURRENT#`. They do not overwrite official `CAMPAIGN` records.

## Campaign Cleanup

Use this to delete generated campaign drafts and start fresh while preserving
`top10_history`.

Dry run official campaign deletion:

```bash
python3 tools/clear-campaigns.py teleport-dev-muddys-top-10
```

Delete official campaign records:

```bash
python3 tools/clear-campaigns.py teleport-dev-muddys-top-10 --write
```

Also delete current-week test campaign records:

```bash
python3 tools/clear-campaigns.py teleport-dev-muddys-top-10 --include-tests --write
```

The script deletes only records from the stack's `ChartCampaignsTableName` with
`pk=CAMPAIGN`, and optionally `pk=CAMPAIGN_TEST`. It does not touch
`TOP10_HISTORY` records or the chart history table.

## Environment export/import

Use these scripts to copy all application DynamoDB data between deployed environments, such as prod to dev.

```bash
# Export from source stack in the current AWS account/region
python3 tools/export-dynamodb-data.py teleport-prod-muddys-top-10

# Preview import into target stack
python3 tools/import-dynamodb-data.py teleport-dev-muddys-top-10 dynamodb-export-teleport-prod-muddys-top-10-YYYYMMDDTHHMMSSZ.json --dry-run

# Import into target stack
python3 tools/import-dynamodb-data.py teleport-dev-muddys-top-10 dynamodb-export-teleport-prod-muddys-top-10-YYYYMMDDTHHMMSSZ.json
```

Both scripts require the AWS CLI, take stack names, and derive table names from CloudFormation outputs. `TracksTableName` and `ConfigTableName` are required; `ChartHistoryTableName` and `ChartCampaignsTableName` are exported/imported when present for newer stacks. The export format uses DynamoDB AttributeValue JSON for lossless reimport.

## clean-history.py

Clean existing track names using CLEAN_TITLES.MD logic.

### What It Does

- Scans all tracks in DynamoDB
- Applies `clean_track_title()` function to each
- Finds tracks where cleaned name differs from current name
- Updates the `track` field with cleaned version

### Usage

**Dry Run** (see what would change):
```bash
python3 clean-history.py
```

**Output**:
```
📊 Scanning DynamoDB table...
✅ Found 1,234 total records

🔍 Analyzing tracks for cleaning...

⚠️  Found 45 tracks that need cleaning:

1. Original: Artist - Song Title [Xtendz] - Clean
   Cleaned:  Artist - Song Title

2. Original: DJ Pool Artist feat. Someone - Track (Club Remix)
   Cleaned:  DJ Pool Artist ft. Someone - Track

   ... and 43 more

🔍 DRY RUN: Would clean 45 track names
   Run with --update flag to actually update
```

**Actually Clean** (update DynamoDB):
```bash
python3 clean-history.py --update
```

**Output**:
```
🧹 Cleaning 45 track names...
   Updated 10/45...
   Updated 20/45...
   Updated 30/45...
   Updated 40/45...

✅ Updated 45 tracks
```

### What Gets Cleaned

Based on CLEAN_TITLES.MD rules:

**Pool/Source Tags Removed**:
- `[Xtendz]`, `[Single]`, `[Club]`, `[DMS]`, etc.

**Quality Markers Removed**:
- `- Clean`, `- Dirty`, `- HD`, `- qHD`, `- 1080`
- `(Clean)`, `(Dirty)`, `(Explicit Edit)`

**DJ/Radio Markers Removed**:
- `(Lyric Video)`, `(Radio)`, `(DJ Beats)`
- BPM markers: `[128-70]`, `(Transition 128-70)`

**Remix Info Removed**:
- `(Club Remix)`, `(Radio Edit)`, `(Extended Mix)`

**Featuring Credits Normalized**:
- `feat.` → `ft.`
- `featuring` → `ft.`

**"n" Normalized**:
- `Artist n Other` → `Artist & Other`

### Examples

**Before → After**:
```
Artist - Song [Xtendz] - Clean
→ Artist - Song

DJ Pool - Track feat. Someone (Club Remix)
→ DJ Pool - Track ft. Someone

Calvin Harris n Dua Lipa - Miracle
→ Calvin Harris & Dua Lipa - Miracle

Track Name (Radio) - HD
→ Track Name
```

### Promotional Content

These are **NOT** cleaned (passed through as-is):
- `Muddy's Music Cafe - ...`
- `MUDDY's - DJ ... on MIC`
- URLs (`http://`, `https://`)
- `Send your ...`

### Safe to Run

- ✅ Dry run by default (won't update unless `--update` flag)
- ✅ Only updates `track` field
- ✅ Doesn't touch canonical_track, validation_status, etc.
- ✅ Uses same logic as poller (consistent results)
- ✅ No data loss

### When to Run

**Run this script if**:
- You have old tracks with dirty names
- You updated CLEAN_TITLES.MD rules
- You want consistent naming in history
- You're seeing pool tags or quality markers in UI

**Don't run if**:
- All your tracks are already clean
- You want to preserve original stream metadata

### Impact on Validation

After cleaning, tracks may be re-validated:
- Validator checks `track` field for duplicates
- If `track` changes, next poll may trigger validation
- Canonical names will be updated to match cleaned names

To force re-validation of all tracks, delete `validation_status` field (separate script needed).

### Performance

- Scans entire table (may take 1-2 minutes for large datasets)
- Updates in batches (shows progress every 10 records)
- No throttling issues (DynamoDB on-demand handles burst)

### Logs

No CloudWatch logs (runs locally). Output goes to terminal only.

---

## find-duplicates.py

Find and remove duplicate tracks from Lambda cold start issues.

### Usage

**Find duplicates**:
```bash
python3 find-duplicates.py
```

**Delete duplicates**:
```bash
python3 find-duplicates.py --delete
```

See script output for detailed usage.

---

## Test Scripts

### test-validation.py

Test track validation against MusicBrainz/Spotify:

```bash
python3 test-validation.py "Artist - Song Title"
```

### test-parser.py

Test Shoutcast metadata parsers:

```bash
python3 test-parser.py
```

---

## Maintenance Workflow

### Initial Setup (After First Deploy)

1. **Configure filters**:
   ```bash
   ./configure-filters.sh
   ```

2. **Clean existing history** (if needed):
   ```bash
   python3 clean-history.py
   python3 clean-history.py --update  # if looks good
   ```

3. **Find duplicates** (if any):
   ```bash
   python3 find-duplicates.py
   python3 find-duplicates.py --delete  # if found
   ```

### Regular Maintenance

**After updating CLEAN_TITLES.MD**:
```bash
# Clean any new tracks with old naming
python3 clean-history.py --update
```

**After fixing cold start issues**:
```bash
# Remove duplicate entries
python3 find-duplicates.py --delete
```

**When testing new filters**:
```bash
# See what would be filtered
curl "$API_URL/config" | jq .top10_filters
curl "$API_URL/top10" | jq '.top10[].track'
```

### Backup Before Major Changes

```bash
# Export current config
curl "$API_URL/config" > config-backup.json

# Export sample of tracks
aws dynamodb scan \
    --table-name muddys-now-playing-tracks \
    --limit 100 > tracks-sample.json
```

---

## Script Safety

All scripts:
- ✅ Default to dry-run (report only)
- ✅ Require explicit flag to make changes
- ✅ Show what will happen before doing it
- ✅ Can be run multiple times safely
- ✅ No side effects on other systems
