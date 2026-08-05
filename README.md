# Muddy's Music Cafe - Top 10 Tracker

A serverless AWS application that monitors [Muddy's Music Cafe](http://muddys.digistream.info:20398/) radio stream, tracks played songs, computes weekly Top 10 charts, and generates AI-powered promotional campaigns.

**📻 For Listeners:** [Listener Guide](docs/LISTENER_GUIDE.md) — how DJ playout and requests create the weekly chart.

---

## What It Does

- 🎵 Polls Shoutcast stream every minute, logs track plays
- ✅ Validates track names against MusicBrainz/Spotify
- 📊 Computes weekly Top 10 with movement indicators
- 🧠 Generates campaign assets using Claude Sonnet (radio reads, social posts, infographic PNG)
- 📥 Renders 1280×720 branded infographic from chart data
- 🌐 Publishes a public welcome page with the latest approved or published campaign PNG
- 🔄 Feedback loop: reviewer preferences shape future generations via AgentCore Memory

## Architecture

```
Stream → Poller (1min) → DynamoDB → Validator → Canonical tracks
                                        ↓
                    API Gateway ← Cognito Auth ← Admin UI (S3+CloudFront)
                                        ↓
    Playlist Generator (weekly) → Chart History snapshots
                                        ↓
    Campaign Generator → AgentCore Runtime → AgentCore Tools
        → Claude generates editorial content (radio/social/infographic)
        → Infographic Renderer (Playwright) → 1280×720 PNG → S3
        → Campaign saved to DynamoDB with immutable revision
```

**Full architecture docs:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Infrastructure | AWS SAM (CloudFormation) |
| Compute | Lambda (Python 3.14 + Node.js 20.x) |
| Database | DynamoDB (4 tables) |
| Auth | Cognito + API Gateway |
| Frontend | Vanilla JS (S3 + CloudFront) |
| AI | Claude Sonnet 4.6 via Bedrock Runtime |
| Orchestration | AgentCore Runtime + Gateway + Memory |
| Infographic | HTML/CSS template + Playwright → PNG |

## Quick Start

```bash
# Prerequisites: AWS CLI, SAM CLI, Docker, Python 3.14

# Deploy
./deploy.sh --env teleport-dev \
  --campaign-model-id global.anthropic.claude-sonnet-4-6 \
  --campaign-model-endpoint bedrock-runtime \
  --campaign-model-arn arn:aws:bedrock:us-west-2:ACCOUNT_ID:inference-profile/global.anthropic.claude-sonnet-4-6 \
  --force-agentcore-runtime-update
```

**Full deployment guide:** [docs/TECHNICAL.md](docs/TECHNICAL.md)

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and data flows |
| [TECHNICAL.md](docs/TECHNICAL.md) | Deployment, configuration, project structure |
| [USER_GUIDE.md](docs/USER_GUIDE.md) | Admin UI guide |
| [docs/](docs/README.md) | Full documentation index |

## Project Structure

```
src/
├── poller/              # Stream polling Lambda
├── validator/           # Track validation Lambda
├── api/                 # REST API Lambda
├── campaign-generator/  # Triggers AgentCore Runtime
├── agentcore-runtime/   # Strands Agent routing
├── agentcore-tools/     # Campaign orchestration
├── infographic-renderer/# Chart poster template + Playwright
├── playlist-generator/  # Spotify integration
└── schedule-updater/    # EventBridge schedule sync
layers/common/           # Shared Python modules
frontend/                # Public welcome page + admin UI (HTML/JS)
docs/                    # Documentation
docs/agentic/context/    # AI steering context files
```

## License

MIT
