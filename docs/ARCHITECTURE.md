# Architecture Overview

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                               │
│                                                                 │
│  ┌──────────────┐         ┌─────────────────┐                 │
│  │ EventBridge  │         │  Stream Poller  │                 │
│  │   Rule       │────────▶│     Lambda      │                 │
│  │ (every 1min) │         │                 │                 │
│  └──────────────┘         └────────┬────────┘                 │
│                                    │                           │
│                                    │ Write                     │
│                                    ▼                           │
│                           ┌─────────────────┐                 │
│                           │   DynamoDB      │                 │
│                           │  Tracks Table   │                 │
│  ┌──────────────┐         │                 │                 │
│  │ API Gateway  │         │  Config Table   │                 │
│  │              │         └─────────────────┘                 │
│  │  GET  /      │                  ▲                           │
│  │  GET  /api/* │                  │ Read/Write               │
│  │  PUT  /api/* │                  │                           │
│  └──────┬───────┘         ┌────────┴────────┐                 │
│         │                 │   API Handler   │                 │
│         └────────────────▶│     Lambda      │                 │
│                           │                 │                 │
│                           │  - History      │                 │
│                           │  - Top 10       │                 │
│                           │  - Config       │                 │
│                           │  - Frontend     │                 │
│                           └─────────────────┘                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ HTTP GET
                                    │
                         ┌──────────┴──────────┐
                         │  Shoutcast Stream   │
                         │  muddys.digistream  │
                         └─────────────────────┘
                                    ▲
                                    │ Listen
                                    │
                              ┌─────┴─────┐
                              │   Users   │
                              │  Browser  │
                              └───────────┘
```

## Data Flow

### 1. Track Polling Flow

```
EventBridge (1 min) → Poller Lambda → HTTP GET Stream
                                    ↓
                            Parse current track
                                    ↓
                        Compare with last track
                                    ↓
                    If changed → DynamoDB Tracks Table
                    If same → Skip
```

### 2. History Query Flow

```
User → API Gateway (/api/history) → API Lambda
                                        ↓
                    Query DynamoDB (last 7 days)
                                        ↓
                            Group by 2-hour blocks
                                        ↓
                                Return JSON
```

### 3. Top 10 Query Flow

```
User → API Gateway (/api/top10) → API Lambda
                                      ↓
                        Get config (chart time)
                                      ↓
                    Query current week tracks
                                      ↓
                    Query previous week tracks
                                      ↓
                        Count & rank tracks
                                      ↓
                    Calculate movement indicators
                                      ↓
                            Return JSON
```

## DynamoDB Access Patterns

### Tracks Table

**Pattern 1: Write new track**
- Operation: `PutItem`
- Key: `pk=TRACK, sk=TS#{timestamp}`
- Used by: Poller Lambda

**Pattern 2: Query recent tracks**
- Operation: `Query` on timestamp-index
- Key: `pk=TRACK, timestamp >= {7_days_ago}`
- Used by: API Lambda (History)

**Pattern 3: Query week range**
- Operation: `Query` on timestamp-index
- Key: `pk=TRACK, timestamp BETWEEN {week_start} AND {week_end}`
- Used by: API Lambda (Top 10)

### Chart History Table

**Pattern 1: Upsert weekly Top 10 snapshot**
- Operation: `PutItem`
- Key: `pk=TOP10_HISTORY, sk=WEEK#{week_id}`
- Used by: API Lambda (`GET /api/top10`) and Playlist Generator Lambda

**Pattern 2: Query recent chart snapshots**
- Operation: `Query`
- Key: `pk=TOP10_HISTORY`, optionally `sk BETWEEN WEEK#{from} AND WEEK#{to}`
- Used by: API Lambda (`GET /api/top10/history`) for index, range, paged, and full-detail reads

**Pattern 3: Get one chart snapshot**
- Operation: `GetItem`
- Key: `pk=TOP10_HISTORY, sk=WEEK#{week_id}`
- Used by: API Lambda (`GET /api/top10/history/{week_id}`)

### Chart Campaigns Table

**Pattern 1: Upsert generated campaign draft**
- Operation: `PutItem`
- Key: `pk=CAMPAIGN, sk=WEEK#{week_id}`
- Used by: Campaign Generator Lambda and API Lambda (`POST /api/campaigns/generate`)

**Pattern 2: Query campaign draft index**
- Operation: `Query`
- Key: `pk=CAMPAIGN`
- Used by: API Lambda (`GET /api/campaigns`)

**Pattern 3: Get or update campaign draft**
- Operation: `GetItem` / `UpdateItem`
- Key: `pk=CAMPAIGN, sk=WEEK#{week_id}`
- Used by: API Lambda campaign review endpoints

### Config Table

**Pattern 1: Get config**
- Operation: `GetItem`
- Key: `configKey={key}`
- Used by: API Lambda

**Pattern 2: Update config**
- Operation: `PutItem`
- Key: `configKey={key}`
- Used by: API Lambda

## Lambda Functions

### Stream Poller

**Trigger:** EventBridge (rate: 1 minute)
**Runtime:** Python 3.14
**Memory:** 256 MB
**Timeout:** 30 seconds

**Environment Variables:**
- `TRACKS_TABLE`: DynamoDB table name
- `CONFIG_TABLE`: DynamoDB table name
- `STREAM_URL`: Shoutcast metadata URL

**IAM Permissions:**
- DynamoDB: PutItem on Tracks Table
- DynamoDB: GetItem on Config Table
- CloudWatch Logs: Write

### API Handler

**Trigger:** API Gateway (HTTP API)
**Runtime:** Python 3.14
**Memory:** 256 MB
**Timeout:** 30 seconds

**Endpoints:**
- `GET /` - Serve frontend HTML
- `GET /api/history` - Track history
- `GET /api/top10` - Top 10 chart
- `GET /api/top10/history` - Weekly Top 10 snapshot index
- `GET /api/top10/history/{week_id}` - Weekly Top 10 snapshot detail
- `GET /api/config` - Get configuration
- `PUT /api/config` - Update configuration
- `GET /api/campaigns` - Campaign draft index
- `GET /api/campaigns/{week_id}` - Campaign draft detail
- `POST /api/campaigns/generate` - Manual campaign generation/regeneration
- `PUT /api/campaigns/{week_id}` - Edit campaign draft content
- `PUT /api/campaigns/{week_id}/status` - Update campaign review status

**Environment Variables:**
- `TRACKS_TABLE`: DynamoDB table name
- `CONFIG_TABLE`: DynamoDB table name
- `CHART_HISTORY_TABLE`: DynamoDB chart snapshot table name
- `CAMPAIGNS_TABLE`: DynamoDB campaign draft table name

**IAM Permissions:**
- DynamoDB: Query, GetItem on Tracks Table
- DynamoDB: GetItem, PutItem on Config Table
- DynamoDB: Query, GetItem, PutItem on Chart History Table
- DynamoDB: Query, GetItem, PutItem, UpdateItem on Chart Campaigns Table
- CloudWatch Logs: Write

### Campaign Generator

**Trigger:** EventBridge Scheduler (`CampaignGenerationSchedule`) using `America/Los_Angeles`
**Runtime:** Python 3.14
**Memory:** 512 MB
**Timeout:** 60 seconds

**Purpose:** Generate weekly campaign drafts outside Cognito user scope.

This function snapshots the countable chart window first, then invokes
AgentCore Runtime with a `create_chart_campaign` action for that explicit
week. The countable window runs from chart reset to campaign generation; the
freeze window between campaign generation and reset is retained in raw track
history but excluded from Top 10 calculations to avoid show play-out bias.

**Environment Variables:**
- `AGENTCORE_RUNTIME_ARN`: AgentCore Runtime ARN for campaign orchestration
- `AGENTCORE_RUNTIME_QUALIFIER`: Runtime endpoint qualifier, normally `DEFAULT`

**IAM Permissions:**
- DynamoDB: Query on Tracks Table
- DynamoDB: GetItem on Config Table
- DynamoDB: PutItem on Chart History Table
- AgentCore: Invoke AgentCore Runtime
- CloudWatch Logs: Write

### AgentCore Tools

**Trigger:** AgentCore Gateway Lambda target
**Runtime:** Python 3.14
**Memory:** 512 MB
**Timeout:** 60 seconds

**Purpose:** Provide an IAM-authenticated MCP-style tool surface for agents
without routing through API Gateway or Cognito.

**Gateway:** Required AgentCore Gateway.
**Memory:** Required AgentCore Memory.

**Tools:**
- `get_current_chart`
- `list_chart_weeks`
- `get_chart_week`
- `get_chart_range`
- `create_chart_brief`
- `create_radio_reads`
- `create_infographic_content`
- `create_social_posts`
- `create_chart_campaign`
- `list_chart_campaigns`
- `get_chart_campaign`
- `update_chart_campaign_status`

**IAM Permissions:**
- Gateway role can invoke only `AgentCoreToolsFunction`
- Tool Lambda can read chart history and config
- Tool Lambda can read/write campaign drafts
- Tool Lambda can retrieve/write AgentCore Memory
- Tool Lambda does not require Cognito user tokens

## Shared Layer

**Purpose:** Common utilities shared between Lambda functions

**Contents:**
- `common.py`: Utility functions
  - Timestamp helpers
  - Week calculation
  - Hour block grouping
  - JSON encoding for Decimal
  - API response formatting
  - CORS headers
- `chart_brief.py`: Deterministic chart brief generation from Top 10 snapshots
- `campaign_generation.py`: Structured campaign draft generation
- `campaign_store.py`: DynamoDB access helpers for campaign workflows
- `agent_context.py`: Agent spec and personal context metadata loading

## Frontend Architecture

**Hosting:** Embedded in API Lambda (served at `/`)
**Type:** Single-page application (SPA)
**Framework:** Vanilla JavaScript (no dependencies)

**Components:**
1. Navigation (History / Top 10)
2. History View (2-hour blocks)
3. Top 10 View (ranked list)
4. API Client (fetch)

**Styling:** Inline CSS with responsive design

## Scalability Considerations

**Current Capacity:**
- Poller: 1 invocation per minute = 43,200 invocations/month
- DynamoDB: On-demand (auto-scales)
- API Gateway: 10,000 requests per second limit (unlikely to hit)

**Data Volume:**
- ~1 track per 3 minutes average
- ~480 tracks per day
- ~3,360 tracks per week
- ~14,400 tracks per month
- TTL: Not currently configured; records are retained until manually deleted or the table is deleted

**Cost Optimization:**
- On-demand DynamoDB (no idle capacity costs)
- Minimal Lambda memory (256 MB)
- Retention can be capped later with DynamoDB TTL if storage growth requires it
- No NAT Gateway required (public AWS service endpoints)

## Security

**Current:**
- Cognito authentication on app API endpoints
- CORS enabled for all origins
- IAM roles use least-privilege
- SSL for API Gateway
- No secrets in code (stream URL in env var)

**Production Recommendations:**
- Add more granular authorization if roles/groups are introduced later
- Restrict CORS to specific origins
- Enable AWS WAF for DDoS protection
- Add request throttling
- Enable API Gateway logging
- Use Secrets Manager for stream URL if needed
- Enable DynamoDB point-in-time recovery

## Monitoring

**CloudWatch Metrics:**
- Lambda invocations
- Lambda errors
- Lambda duration
- DynamoDB read/write capacity
- API Gateway requests
- API Gateway 4xx/5xx errors

**CloudWatch Logs:**
- Lambda function logs
- API Gateway access logs (optional)

**Alarms (Recommended):**
- Poller Lambda errors > 5 in 5 minutes
- API Lambda errors > 10 in 5 minutes
- DynamoDB throttling events

## Disaster Recovery

**Backup Strategy:**
- DynamoDB: On-demand backups (manual)
- Option: Enable point-in-time recovery
- Code: Version controlled in Git

**Recovery Time Objective (RTO):**
- ~5 minutes (redeploy SAM stack)

**Recovery Point Objective (RPO):**
- 1 minute (track data loss = time since last poll)

## Future Enhancements

**Potential Features:**
- WebSocket for real-time updates
- User favorites/playlists
- Historical chart comparison (month-over-month)
- Export to CSV/PDF
- Admin dashboard
- Multiple streams support
- Track metadata enrichment (album art, etc.)
- Social sharing
- Email/SMS notifications for favorite tracks
