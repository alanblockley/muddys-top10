# System Architecture

Serverless AWS application that monitors a Shoutcast internet radio stream, tracks played songs, validates against MusicBrainz/Spotify, computes weekly Top 10 charts, and generates AI-powered marketing campaigns (infographic PNG, social posts, radio reads).

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Shoutcast Stream                                                               │
│  (muddys.digistream.info:20398)                                                 │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │ HTTP poll every 1min
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  EventBridge Schedules                                                           │
│  ├── Stream poll (1min)                                                          │
│  ├── Chart snapshot (weekly, configurable)                                       │
│  └── Campaign generation (weekly, after chart)                                   │
└───────┬──────────────────────────────┬───────────────────────────┬───────────────┘
        │                              │                           │
        ▼                              ▼                           ▼
┌───────────────────┐  ┌──────────────────────────┐  ┌─────────────────────────────┐
│ StreamPoller      │  │ PlaylistGenerator        │  │ CampaignGenerator           │
│ Function          │  │ Function                 │  │ Function                    │
│ (Python 3.14)     │  │ (Python 3.14)            │  │ (Python 3.14)               │
└────────┬──────────┘  └────────────┬─────────────┘  └──────────────┬──────────────┘
         │                          │                                │
         ▼                          ▼                                ▼
┌──────────────────────────────────────────────┐    ┌───────────────────────────────┐
│  DynamoDB                                    │    │  AgentCore Runtime            │
│  ├── Tracks Table (stream: NEW_IMAGE)        │    │  (Strands Agent)              │
│  ├── Config Table                            │    └───────────────┬───────────────┘
│  ├── ChartHistory Table                      │                    │
│  └── ChartCampaigns Table                    │                    ▼
└───────────┬──────────────────────────────────┘    ┌───────────────────────────────┐
            │ DynamoDB Stream                        │  AgentCore Gateway            │
            ▼                                       └───────────────┬───────────────┘
┌───────────────────────┐                                           │
│ TrackValidator        │                                           ▼
│ Function              │                           ┌───────────────────────────────┐
│ (Python 3.14)         │                           │  AgentCoreTools Function      │
└───────┬───────┬───────┘                           │  (Python 3.14)                │
        │       │                                   │  MCP tool surface             │
        ▼       ▼                                   └───────┬───────────────┬───────┘
┌────────────┐ ┌────────────┐                               │               │
│MusicBrainz│ │ Spotify    │                               ▼               ▼
│ API        │ │ API        │               ┌──────────────────┐  ┌─────────────────┐
└────────────┘ └────────────┘               │ Bedrock          │  │ Infographic     │
                                            │ (Claude Sonnet   │  │ Renderer        │
                                            │  4.6)            │  │ (Node.js 20.x)  │
┌───────────────────────────────────────┐   └──────────────────┘  └────────┬────────┘
│  API Gateway + Cognito                │                                  │
│  (REST API, 26+ routes)              │                                  ▼
└───────────────┬───────────────────────┘                       ┌─────────────────┐
                │                                               │ S3 Bucket       │
                ▼                                               │ (PNG assets)    │
┌───────────────────────────────────┐                           └─────────────────┘
│  ApiFunction (Python 3.14)        │
│  ├── /api/top10                   │
│  ├── /api/top10/history           │
│  ├── /api/campaigns               │
│  ├── /api/history                 │
│  ├── /api/config                  │
│  └── /api/health                  │
└───────────────────────────────────┘

┌───────────────────────────────────────┐   ┌───────────────────────────────────┐
│  S3 + CloudFront                      │   │  AgentCore Memory                 │
│  (Static frontend, HTTPS)             │   │  (Feedback + editorial context)   │
└───────────────────────────────────────┘   └───────────────────────────────────┘

┌───────────────────────────────────┐
│  ScheduleUpdater Function         │
│  (Python 3.14)                    │
│  Syncs EventBridge from config    │
└───────────────────────────────────┘
```

## Lambda Functions

| # | Function | Runtime | Trigger | Purpose |
|---|----------|---------|---------|---------|
| 1 | StreamPollerFunction | Python 3.14 | EventBridge (1min) | Polls Shoutcast stream, writes new tracks to DynamoDB |
| 2 | TrackValidatorFunction | Python 3.14 | DynamoDB Streams (NEW_IMAGE) | Validates tracks against MusicBrainz/Spotify, canonicalizes names |
| 3 | ApiFunction | Python 3.14 | API Gateway | REST API with Cognito auth, 26+ routes for chart/history/campaigns/config |
| 4 | CampaignGeneratorFunction | Python 3.14 | EventBridge (weekly) / API | Invokes AgentCore Runtime to orchestrate campaign generation |
| 5 | InfographicRendererFunction | Node.js 20.x | Lambda invoke | Renders HTML/CSS chart poster to 1280x720 PNG via Playwright |
| 6 | PlaylistGeneratorFunction | Python 3.14 | EventBridge (weekly) | Generates Spotify playlist, persists weekly chart snapshot to ChartHistory |
| 7 | ScheduleUpdaterFunction | Python 3.14 | Config change | Syncs EventBridge schedule rules when chart generation config changes |
| 8 | AgentCoreToolsFunction | Python 3.14 | AgentCore Gateway | Lambda-backed MCP tools for chart/campaign operations |

## Infrastructure

### DynamoDB Tables

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| Tracks | `pk=TRACK`, `sk=TS#{timestamp}` | Track play history with validation metadata. GSI on timestamp. Stream enabled (NEW_IMAGE). |
| Config | `configKey` | Application configuration (chart schedule, filters, feature flags) |
| ChartHistory | `pk=TOP10_HISTORY`, `sk=WEEK#{week_id}` | Persisted weekly Top 10 snapshots with movement data |
| ChartCampaigns | `pk=CAMPAIGN`, `sk=WEEK#{week_id}` | Generated campaign drafts with revision history |

### Auth & Networking

- **API Gateway**: REST API with Cognito authorizer
- **Cognito User Pool**: JWT-based authentication for all API and frontend access
- **CloudFront**: HTTPS CDN with OAC for S3 origin
- **S3**: Static frontend hosting + campaign asset storage (infographic PNGs)

### AI & Agent Infrastructure

- **AgentCore Runtime**: Strands Agent execution environment for campaign orchestration
- **AgentCore Gateway**: IAM-authenticated MCP tool surface (no Cognito, no API Gateway)
- **AgentCore Memory**: Semantic storage for feedback and editorial continuity
- **Bedrock**: Claude Sonnet 4.6 via bedrock-runtime for text generation (radio reads, social posts, infographic copy)

### Scheduling

- **EventBridge**: Stream polling (1min), weekly chart snapshot, weekly campaign generation
- **ScheduleUpdaterFunction**: Keeps EventBridge schedules in sync when config changes via admin UI

## Campaign Generation Flow

```
EventBridge (weekly)              API (manual trigger)
        │                                │
        └────────────┬───────────────────┘
                     ▼
        ┌─────────────────────────┐
        │ CampaignGeneratorFunction│
        └────────────┬────────────┘
                     │ invoke
                     ▼
        ┌─────────────────────────┐
        │ AgentCore Runtime       │
        │ (Strands Agent)         │
        └────────────┬────────────┘
                     │ MCP tool calls
                     ▼
        ┌─────────────────────────┐
        │ AgentCoreToolsFunction  │
        │                         │
        │ 1. get_chart_brief      │──→ ChartHistory table
        │ 2. get_feedback         │──→ AgentCore Memory (semantic search)
        │ 3. generate_editorial   │──→ Bedrock (Claude Sonnet 4.6)
        │ 4. render_infographic   │──→ InfographicRendererFunction
        │ 5. save_campaign        │──→ ChartCampaigns table
        └─────────────────────────┘
```

### Step Details

1. **Chart Brief**: Builds deterministic facts from ChartHistory — rankings, movement, play counts, week-over-week deltas
2. **Feedback Retrieval**: Queries AgentCore Memory for prior reviewer feedback via semantic search
3. **Editorial Generation**: Claude Sonnet 4.6 generates radio reads, social posts, and infographic copy (Chart Talk cells) using chart_brief + feedback context
4. **Infographic Rendering**: InfographicRendererFunction receives chart_data, renders `chart-poster.js` HTML/CSS template to 1280x720 PNG via Playwright, stores in S3
5. **Campaign Storage**: Full campaign saved to ChartCampaigns table as immutable revision

### Infographic Renderer Detail

- `chart-poster.js`: Data-driven HTML/CSS template
- Font Awesome icons for movement indicators
- Background image, logo, FA font loaded as base64 data URIs (no network dependencies at render time)
- Chart Talk: 6 cells, each highlighting a different artist with AI-generated or auto-fallback commentary
- Output: 1280x720 PNG stored in S3

## Feedback Loop

```
Reviewer (Admin UI)
        │
        │ PUT /api/campaigns/{week_id} (feedback/review)
        ▼
┌───────────────────┐
│ ApiFunction       │
│ 1. Store in DB    │──→ ChartCampaigns table (review field)
│ 2. Write memory   │──→ AgentCore Memory
└───────────────────┘

        ... next week ...

┌─────────────────────────┐
│ AgentCoreToolsFunction  │
│ get_feedback tool        │──→ AgentCore Memory (semantic search)
│                         │    retrieves past preferences
│ generate_editorial       │──→ Claude adjusts tone/style
└─────────────────────────┘
```

Reviewer feedback persists across generations. AgentCore Memory provides semantic retrieval so Claude adapts to editorial preferences without explicit rules.

## Deployment

- **SAM** (Serverless Application Model) for IaC
- `template.yaml` defines all resources
- `deploy.sh` wraps `sam build --use-container` + `sam deploy`
- Multi-environment via `samconfig.toml` sections (`prod`, `dev`)
- Frontend deployed to S3 with CloudFront invalidation

## Security Model

- All API routes require Cognito JWT authentication
- Scheduled workloads (campaign generation) run under IAM, not Cognito
- AgentCore Gateway uses IAM auth with dedicated gateway role
- CloudFront enforces HTTPS with OAC for S3
- DynamoDB encrypted at rest
- Least-privilege IAM policies per function
