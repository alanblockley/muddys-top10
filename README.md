# Muddy's Music Cafe - Top 10 Tracker

A serverless AWS application that monitors [Muddy's Music Cafe](http://muddys.digistream.info:20398/) radio stream, tracks played songs, and displays a Top 10 chart with week-over-week movement indicators.

**📻 For Listeners:** Want to understand how the Top 10 works? Check out the [Listener Guide](docs/LISTENER_GUIDE.md) - explains how DJ playout and customer requests create the weekly chart!

---

## Architecture

**AWS Services Used:**
- **Lambda**: Stream poller, track validator, API handlers, playlist generator, and campaign generator
- **DynamoDB**: Track history, configuration, weekly chart snapshots, and campaign draft storage
- **API Gateway**: REST API with Cognito authorizer
- **Cognito**: User authentication for admin panel
- **S3 + CloudFront**: Static website hosting and CDN
- **EventBridge**: Scheduled stream polling and weekly campaign generation
- **AgentCore Gateway**: Optional IAM-authenticated MCP tool surface for chart/campaign agents
- **SAM**: Infrastructure as Code deployment

**Features:**
- 🎵 Automatic track detection and logging
- ✅ Track validation and canonicalization (MusicBrainz/Spotify)
- 📊 Login-gated Top 10 chart with weekly rankings
- 📈 Track movement indicators (up/down/new/same)
- 📥 Social media export - download Top 10 as stylized infographic
- 🧠 Scheduled agentic campaign drafts for radio reads, infographic copy, and social posts
- 🛠️ Required AgentCore Gateway Lambda target for MCP-style chart/campaign tools
- 🔒 Protected history and admin views
- ⏰ History view with 2-hour blocks in PST timezone
- 🎚️ Configurable Top 10 filters (regex patterns)
- ⚙️ Configurable chart generation time
- 🌐 Responsive web UI with radio station theme
- 🔐 Admin panel with Cognito authentication
- 🔧 Configurable stream URL via SAM parameter
- 🎨 Title cleaning and normalization
- 🔄 Backup stream status indicator (XML format only)

## Project Structure

```
.
├── template.yaml                    # SAM template (infrastructure)
├── samconfig.toml                  # SAM deployment config
├── deploy.sh                        # Main deployment script
├── src/
│   ├── poller/                     # Stream poller Lambda
│   │   └── app.py
│   ├── validator/                  # Track validator Lambda
│   │   └── app.py
│   └── api/                        # API handler Lambda
│       └── app.py
├── layers/
│   └── common/                     # Shared utilities layer
│       ├── common.py               # General utilities
│       ├── track_normalizer.py    # Track parsing & scoring
│       └── music_providers.py     # MusicBrainz/Spotify APIs
├── frontend/
│   ├── index.html                  # Login-gated Top 10 view
│   ├── admin.html                  # Admin panel (auth required)
│   ├── data-viewer.html            # Raw data viewer
│   └── assets/
│       └── muddys-logo.png         # Cafe logo
├── docs/                           # Documentation
│   ├── README.md                   # Documentation index
│   ├── ARCHITECTURE.md             # System architecture
│   ├── TRACK_VALIDATION.md         # Validation system
│   ├── CLEAN_TITLES.MD             # Title cleaning rules
│   └── ...                         # More documentation
├── scripts/                        # Utility scripts
│   ├── update-frontend.sh          # Frontend-only update
│   └── configure-filters.sh        # Setup filters
├── tests/                          # Test scripts
│   ├── test-validation.py          # Test track validation
│   ├── test-cleaning.py            # Test title cleaning
│   └── test-parser.py              # Test format parsing
└── tools/                          # Maintenance tools
    ├── clean-history.py            # Backfill title cleaning
    ├── revalidate-history.py       # Re-validate tracks
    └── find-duplicates.py          # Find duplicate entries
```

## Prerequisites

1. **AWS CLI** configured with credentials
2. **AWS SAM CLI** installed ([Install Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
3. **Docker** for containerized SAM builds
4. **AWS Account** with appropriate permissions

## Deployment

### Quick Deploy

```bash
./deploy.sh --env prod
```

This will:
1. Build the SAM application in the Lambda runtime container
2. Use the selected SAM config environment, or ask once and create it
3. Deploy all resources to AWS

Deploy another named environment:

```bash
# Existing environments reuse their samconfig.toml section
./deploy.sh --env prod

# New environments prompt for stack name, region, stream URL, and
# optional Spotify/custom CloudFront hostname settings.
./deploy.sh --env dev
```

Spotify integrations are feature-flagged per environment:

```bash
./deploy.sh --env dev --enable-spotify
./deploy.sh --env dev --disable-spotify
```

For development environments, answer `n` to the custom hostname prompt to deploy with the generated CloudFront domain only.

### Manual Deploy

```bash
# Build using the Lambda runtime container, no matching local Python runtime required
sam build --use-container

# Deploy using a named SAM config environment
sam deploy --config-env prod

# Or use the deploy script
./deploy.sh --env prod
```

### Custom Stream URL

The poller supports both Shoutcast v1 (7.html) and v2 (stats?sid=) formats:

```bash
# Shoutcast v1 format
sam deploy --parameter-overrides StreamUrl=http://your-stream-url:port/7.html

# Shoutcast v2 format
sam deploy --parameter-overrides StreamUrl=http://your-stream-url/stats?sid=1
```

Format is automatically detected. See [STREAM_FORMATS.md](docs/STREAM_FORMATS.md) for details.

### Custom CloudFront Domain

By default the frontend uses the generated CloudFront domain. To use a custom CNAME, create or import an ACM certificate in `us-east-1`, then deploy with both parameters:

```bash
sam deploy --parameter-overrides \
    CustomDomainName=top10.example.com \
    CloudFrontCertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id
```

After deployment, create a DNS CNAME from your custom domain to the `CloudFrontDomainName` stack output.

### AgentCore Runtime and Gateway

Campaign generation now enters through an AgentCore Runtime. Browser/API and
scheduled triggers invoke the runtime; the runtime uses Strands Agent tools to
route campaign actions to the Lambda-backed tool service.

The gateway exposes focused chart/campaign tools backed by
`AgentCoreToolsFunction`; it does not route through API Gateway or Cognito.
AgentCore Gateway is now a required stack resource.

### AgentCore Memory

AgentCore Memory is also required. It lets scheduled and tool-driven campaign
generation retrieve prior weekly campaign context before writing new DJ reads,
infographic copy, and social posts.

Set a custom memory name if needed:

```bash
./deploy.sh --env prod \
    --agentcore-memory-name teleport_prod_agentcore_memory
```

Memory is used only for editorial continuity and preferences. Current
`chart_brief` facts remain authoritative. The deploy script derives memory
names from `teleport-%ENV%-agentcore-memory`, normalized to underscores because
AgentCore Memory names cannot contain hyphens.

### Optional Bedrock Campaign Generation

Campaign drafts use Bedrock-backed JSON generation by default with
`deepseek.v3.2` on the `bedrock-mantle` endpoint. To be explicit:

```bash
./deploy.sh --env prod \
    --campaign-model-id deepseek.v3.2 \
    --campaign-model-endpoint bedrock-mantle
```

To use the Strands OpenAI Responses provider against Mantle, supply a
Secrets Manager ARN containing the Bedrock/Mantle API key:

```bash
./deploy.sh --env prod \
    --campaign-model-id deepseek.v3.2 \
    --campaign-model-endpoint strands-openai-responses \
    --campaign-model-api-key-secret-arn arn:aws:secretsmanager:us-west-2:123456789012:secret:my-bedrock-api-key
```

Clear model-backed generation and return to deterministic drafts:

```bash
./deploy.sh --env prod --clear-campaign-model
```

If model invocation fails, the generator stores deterministic fallback content
and records the model error on that section for review.

Final infographic PNG generation can use a separate image-capable model. This
is intentionally separate from the campaign text/content model:

```bash
./deploy.sh --env prod \
    --campaign-image-model-id IMAGE_MODEL_ID \
    --campaign-image-model-api-key-secret-arn arn:aws:secretsmanager:us-west-2:123456789012:secret:my-image-api-key \
    --campaign-image-size 1280x720
```

When configured, the campaign first tries to create the final PNG from the
stored template reference PNG plus factual chart data. If that fails, it falls
back to the Playwright HTML/CSS renderer.

Campaign prompts can optionally be sourced from Bedrock Prompt Management.
Configure prompt identifiers and versions in Admin UI -> Settings -> Campaign
Prompt Management. Blank prompt identifiers use the built-in production prompts.
Generated campaign metadata records the prompt source/version used for each
section.

### Spotify API (Optional)

For better track validation coverage, add Spotify API credentials:

```bash
sam deploy --parameter-overrides \
    StreamUrl=http://muddys.digistream.info:20398/7.html \
    SpotifyClientId=YOUR_CLIENT_ID \
    SpotifyClientSecret=YOUR_CLIENT_SECRET
```

Get credentials at: https://developer.spotify.com/dashboard

See [TRACK_VALIDATION.md](docs/TRACK_VALIDATION.md) for details.

## Configuration

### First-Time Setup

After deployment, create your first admin user:

```bash
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name teleport-prod-muddys-top-10 \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

aws cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username admin@example.com \
    --user-attributes \
        Name=email,Value=admin@example.com \
        Name=email_verified,Value=true
```

See [COGNITO_SETUP.md](docs/COGNITO_SETUP.md) for user management.

### Top 10 Filters

Configure regex patterns to exclude promotional content from Top 10:

```bash
./scripts/configure-filters.sh
```

This sets up default filters for:
- Station IDs (Muddy's Music Cafe)
- DJ announcements
- URLs and promotional messages

See [FILTERS.md](docs/FILTERS.md) for custom filter patterns.

### Chart Generation Time

Configure weekly chart generation via the admin panel or API:

```bash
curl -X PUT https://your-api-url/api/config \
  -H "Content-Type: application/json" \
  -H "Authorization: YOUR_JWT_TOKEN" \
  -d '{
    "chart_generation": {
      "hour": 0,
      "day": "monday"
    }
  }'
```

**Parameters:**
- `hour`: Hour of day (0-23, UTC) when chart week starts
- `day`: Day of week

### Track Validation

Tracks are automatically validated against MusicBrainz and Spotify to get canonical names:

- **Input**: `HUNTRIX - What It Sounds Like KPop Demon Hunters`
- **Output**: `HUNTR/X - What It Sounds Like`

This corrects typos and normalizes artist/title formatting. See [TRACK_VALIDATION.md](docs/TRACK_VALIDATION.md) for details.

## API Endpoints

### Authenticated Endpoints

#### GET /
Login-gated Top 10 view

#### GET /api/top10
Returns Top 10 tracks with movement indicators. Requires Cognito authentication.

**Response:**
```json
{
  "top10": [
    {
      "rank": 1,
      "track": "Artist - Song Title",
      "play_count": 45,
      "previous_rank": 3,
      "movement": "up",
      "movement_delta": 2
    }
  ],
  "chart_date": "2024-03-18T00:00:00Z",
  "week_start": "2024-03-18T00:00:00Z",
  "week_end": "2024-03-25T00:00:00Z"
}
```

**Movement Types:**
- `up`: Track moved up from previous week
- `down`: Track moved down from previous week
- `same`: Track maintained same position
- `new`: Track is new to Top 10

#### GET /api/top10/history
Lists persisted weekly Top 10 snapshots for trend analysis and AI agent use. Requires Cognito authentication.

Optional query parameter:
- `limit` (Number): Number of weekly index entries to return, default `12`, max `104`
- `from` (String): Inclusive start week in `YYYY-MM-DD`
- `to` (String): Inclusive end week in `YYYY-MM-DD`
- `detail` (Boolean): Return full snapshots instead of index entries when `true`
- `all` (Boolean): Return all matching weeks by paging DynamoDB internally when `true`
- `next_token` (String): Continue a paged index or detail query

Each index entry includes:
- `week_id` (YYYY-MM-DD)
- `href` (`/api/top10/history/YYYY-MM-DD`)
- `week_start` / `week_end`
- `snapshot_key`

#### GET /api/top10/history/{week_id}
Returns the full persisted weekly Top 10 snapshot for a chart week. `week_id` uses `YYYY-MM-DD`, based on the configured chart week start in America/Los_Angeles time. Requires Cognito authentication.

Each snapshot includes:
- `week_id`
- `snapshot_key`
- `week_start` / `week_end`
- `previous_week_start` / `previous_week_end`
- `chart_config`
- `filter_patterns`
- `top10` with rank, play count, previous rank, movement, and movement delta
- `summary` counts for current and previous week

Examples:

```bash
AUTH_HEADER="Authorization: Bearer YOUR_COGNITO_JWT"

# Latest 12 available weeks as an index
curl -H "$AUTH_HEADER" "$API_URL/top10/history"

# Available weeks in a date range
curl -H "$AUTH_HEADER" "$API_URL/top10/history?from=2026-06-01&to=2026-07-20"

# Full snapshots for a date range
curl -H "$AUTH_HEADER" "$API_URL/top10/history?from=2026-06-01&to=2026-07-20&detail=true"

# All full snapshots currently stored
curl -H "$AUTH_HEADER" "$API_URL/top10/history?all=true&detail=true"

# One full weekly snapshot
curl -H "$AUTH_HEADER" "$API_URL/top10/history/2026-07-20"
```

#### GET /api/config
Returns current configuration. Requires Cognito authentication.

**Response:**
```json
{
  "chart_generation": {"hour": 0, "day": "monday"},
  "top10_filters": ["^Muddy'?s Music Cafe", "https?://"]
}
```

#### GET /api/health
Health check endpoint. Requires Cognito authentication.

#### GET /api/campaigns
Lists generated weekly campaign drafts. Requires Cognito authentication.

Optional query parameters:
- `limit` (Number): Number of campaign entries to return, default `20`, max `100`
- `next_token` (String): Continue a paged query

#### GET /api/campaigns/{week_id}
Returns one campaign draft for a chart week. Requires Cognito authentication.

#### GET /api/campaigns/{week_id}/revisions
Lists immutable generated revisions for a campaign week. Requires Cognito
authentication. The main campaign record remains the active snapshot for
backwards-compatible UI/API reads.

#### GET /api/campaigns/{week_id}/revisions/{revision_id}
Returns one immutable generated revision, including generated sections and
stored infographic asset metadata. Requires Cognito authentication.

#### PUT /api/campaigns/{week_id}/revisions/{revision_id}/approve
Approves a specific immutable revision and promotes it as the active campaign
snapshot. Requires Cognito authentication.

#### POST /api/campaigns/generate
Manually generates or regenerates a campaign draft. Requires Cognito authentication.

The scheduled generator runs under IAM without Cognito user scope. This endpoint
is only for human-requested generation from the authenticated app/CLI.

**Body:**
```json
{
  "week_id": "2026-07-20",
  "sections": ["radio", "infographic", "social"]
}
```

`week_id` is optional and defaults to the latest available chart snapshot.
`sections` is optional and defaults to all sections.

#### PUT /api/campaigns/{week_id}
Edits campaign draft content. Requires Cognito authentication.

Editable top-level fields:
- `radio_reads`
- `infographic`
- `social`
- `review`

#### PUT /api/campaigns/{week_id}/status
Updates the review lifecycle status. Requires Cognito authentication.

**Body:**
```json
{
  "status": "approved"
}
```

Allowed statuses: `draft`, `reviewed`, `approved`, `published`.

### Admin Endpoints

#### GET /admin.html
Admin panel with history, filters, and chart configuration

#### GET /api/history
Returns track history grouped by 2-hour blocks (last 7 days, PST timezone)

**Headers:**
```
Authorization: <JWT_TOKEN>
```

**Response:**
```json
{
  "blocks": [
    {
      "block_timestamp": 1711267200,
      "block_label": "2024-03-24 02:00 PM PST",
      "tracks": [
        {
          "timestamp": 1711267890,
          "formatted_time": "2024-03-24T14:31:30-08:00",
          "track": "Taylor Swift - Blank Space",
          "raw_track": "Tayler Swift - Blank Space",
          "validation_status": "validated",
          "artist": "Taylor Swift",
          "title": "Blank Space"
        }
      ]
    }
  ],
  "total_tracks": 1234
}
```

#### PUT /api/config
Updates configuration (filters and chart generation time)

**Headers:**
```
Authorization: <JWT_TOKEN>
Content-Type: application/json
```

**Body:**
```json
{
  "chart_generation": {"hour": 0, "day": "monday"},
  "top10_filters": ["^Muddy'?s Music Cafe", "https?://"]
}
```

## DynamoDB Schema

### Tracks Table

**Primary Key:**
- `pk` (String): Always "TRACK"
- `sk` (String): "TS#{timestamp}"

**Attributes:**
- `timestamp` (Number): Unix timestamp
- `track` (String): Raw/cleaned track name
- `canonical_track` (String): Validated canonical name (if validated)
- `artist` (String): Parsed artist name (if validated)
- `title` (String): Parsed title (if validated)
- `validation_status` (String): "validated" | "unvalidated" | "promotional"
- `validation_confidence` (String): "high" | "medium" | "low"
- `music_db_id` (String): MusicBrainz or Spotify ID (if validated)
- `music_db_source` (String): "musicbrainz" | "spotify" (if validated)
- `artist_score` (Number): Artist match score 0.0-1.0 (if validated)
- `title_score` (Number): Title match score 0.0-1.0 (if validated)
- `total_score` (Number): Overall match score 0.0-1.0 (if validated)
- No TTL is currently configured; track records are retained until manually deleted or the table is deleted.

**GSI: timestamp-index**
- PK: `pk`
- SK: `timestamp`

**Stream:** Enabled (NEW_IMAGE) - triggers TrackValidatorFunction

### Chart History Table

Stores one persisted weekly Top 10 snapshot per chart week for trend analysis.

**Primary Key:**
- `pk` (String): Always "TOP10_HISTORY"
- `sk` (String): "WEEK#{week_id}", for example "WEEK#2026-07-20"

**Attributes:**
- `week_id` (String): Chart week start date in YYYY-MM-DD format
- `snapshot_type` (String): "weekly_top10"
- `week_start_timestamp` / `week_end_timestamp` (Number): Chart week bounds
- `previous_week_start_timestamp` (Number): Prior chart week start
- `generated_at_timestamp` (Number): Last snapshot generation time
- `chart_config` (Map): Chart reset day/hour used
- `filter_patterns` (List): Filters applied during chart calculation
- `top10` (List): Ranked chart entries with movement metadata
- `summary` (Map): Current and previous week play/unique counts

### Chart Campaigns Table

Stores generated weekly campaign drafts for human review.

**Primary Key:**
- `pk` (String): Always "CAMPAIGN"
- `sk` (String): "WEEK#{week_id}", for example "WEEK#2026-07-20"

**Attributes:**
- `week_id` (String): Chart week start date in YYYY-MM-DD format
- `status` (String): "draft" | "reviewed" | "approved" | "published" | "failed"
- `chart_brief` (Map): Deterministic chart facts used by generators
- `radio_reads` (Map): Broadcast-ready radio read draft
- `infographic` (Map): Infographic editorial content draft
- `social` (Map): Social media post drafts
- `generated_at` (String): ISO timestamp
- `generated_by` (String): "scheduled-agent" or "human-request"
- `requested_by` (String): Cognito identity for human-triggered generation, if any
- `source_snapshot_key` (String): Source `top10_history` snapshot key
- `generator` (Map): Prompt/context/spec provenance
- Review timestamps and actors when status changes

### Config Table

**Primary Key:**
- `configKey` (String): Configuration key

**Attributes:**
- `value` (Map): Configuration value

## Frontend UI

### Login-Gated Site (/)
- **Top 10 Chart**: Current week's top tracks
- Modern radio station theme (dark with purple/indigo accents)
- Movement indicators (↑ up, ↓ down, − same, ★ new)
- Play counts
- Chart period display
- Link to admin panel

### Admin Panel (/admin.html)
Protected by Cognito authentication with three tabs:

**📜 History Tab**:
- All tracks from last 7 days
- Grouped into 2-hour blocks (even hours in PST)
- Shows canonical names with validation status
- Most recent blocks first

**🎚️ Filters Tab**:
- Manage Top 10 filter patterns
- Real-time pattern validation
- View currently active filters
- Add/remove patterns

**📊 Chart Config Tab**:
- Set weekly chart generation time
- Configure timezone and day of week

## Monitoring

### CloudWatch Logs

**Stream Poller:** `/aws/lambda/teleport-prod-muddys-top-10-stream-poller`
**Track Validator:** `/aws/lambda/teleport-prod-muddys-top-10-track-validator`
**API Handler:** `/aws/lambda/teleport-prod-muddys-top-10-api`

### View Logs

```bash
sam logs -n StreamPollerFunction --stack-name teleport-prod-muddys-top-10 --tail
sam logs -n TrackValidatorFunction --stack-name teleport-prod-muddys-top-10 --tail
sam logs -n ApiFunction --stack-name teleport-prod-muddys-top-10 --tail
```

### Validation Metrics

Check track validation success rate:

```bash
# Recent validated tracks
aws dynamodb query \
    --table-name teleport-prod-muddys-top-10-tracks \
    --index-name timestamp-index \
    --key-condition-expression "pk = :pk" \
    --expression-attribute-values '{":pk":{"S":"TRACK"}}' \
    --projection-expression "track,canonical_track,validation_status,validation_confidence" \
    --limit 20
```

## Troubleshooting

### Poller not detecting tracks

Check CloudWatch Logs:
```bash
sam logs -n StreamPollerFunction --stack-name muddys-top10 --tail
```

Test stream URL manually:
```bash
curl http://muddys.digistream.info:20398/7.html
```

### Empty Top 10

Wait for data to accumulate. The poller runs every minute, so tracks should appear within a few minutes.

### API Gateway 502 Errors

Check Lambda function logs for errors. Common issues:
- DynamoDB permissions
- Lambda timeout (increase in template.yaml)

## Local Development

### DynamoDB Environment Copy

Export all application DynamoDB data from the current AWS account/region for a stack:

```bash
python3 tools/export-dynamodb-data.py teleport-prod-muddys-top-10
```

Import that export into another deployed stack:

```bash
python3 tools/import-dynamodb-data.py teleport-dev-muddys-top-10 dynamodb-export-teleport-prod-muddys-top-10-YYYYMMDDTHHMMSSZ.json
```

The scripts use the AWS CLI and derive table names from CloudFormation outputs. Tracks and config are required; weekly Top 10 chart history and campaign drafts are included when the stack exposes `ChartHistoryTableName` and `ChartCampaignsTableName`. The import overwrites items with matching keys. Use `--dry-run` to preview target tables and counts.

### Test Poller Lambda Locally

```bash
sam build --use-container
sam local invoke StreamPollerFunction
```

### Test API Lambda Locally

```bash
sam local start-api
curl http://localhost:3000/api/history
```

## Cleanup

Remove all AWS resources:

```bash
sam delete --stack-name muddys-top10
```

This will delete:
- Lambda functions
- DynamoDB tables (all data will be lost)
- API Gateway
- EventBridge rules
- IAM roles

## Cost Estimate

**Expected Monthly Costs (low traffic):**
- Lambda: ~$1.50 (poller + validator + API)
- DynamoDB: ~$2.50 (on-demand pricing + streams)
- API Gateway: ~$0.10
- Cognito: Free tier (50,000 MAUs)
- S3 + CloudFront: ~$0.50
- **Total: ~$5-7/month**

**Cost Optimization:**
- DynamoDB uses on-demand pricing (pay per request)
- No automatic track deletion is currently configured; add DynamoDB TTL if retention needs to be capped
- Lambda functions use minimal memory
- Track validator batches stream events
- MusicBrainz API is free
- Spotify API is free (within limits)

## Security

- **Authenticated Access**: Top 10, history, config, health, and Spotify admin actions require Cognito authentication
- **Scheduled Agentic Work**: Weekly campaign generation runs as an IAM workload, not a Cognito user
- **AgentCore Gateway**: Optional IAM-authenticated MCP access uses a dedicated gateway role and Lambda target
- **Cognito**: AWS managed user authentication with JWT tokens
- **CORS**: Enabled for all origins (API Gateway)
- **IAM**: Least-privilege policies for Lambda functions
- **DynamoDB**: Encrypted at rest, streams enabled
- **CloudFront**: HTTPS enforced, OAC for S3 access

See [SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for detailed security documentation.

## License

MIT

## Support

For issues or questions, please open an issue on GitHub.
