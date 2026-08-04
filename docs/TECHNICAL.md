# Technical Operations

## Deployment

### Prerequisites

- AWS CLI configured with credentials
- AWS SAM CLI
- Docker (for containerised SAM builds)
- Node.js (for infographic renderer)
- Python 3.14

### Deploy Command

```bash
./deploy.sh --env teleport-dev \
    --campaign-model-id global.anthropic.claude-sonnet-4-6 \
    --campaign-model-endpoint bedrock-runtime \
    --campaign-model-arn arn:aws:bedrock:us-west-2:ACCOUNT:inference-profile/global.anthropic.claude-sonnet-4-6 \
    --force-agentcore-runtime-update
```

### deploy.sh Flags

| Flag | Purpose |
|------|---------|
| `--env` | Target environment (prod, teleport-dev) |
| `--campaign-model-id` | Bedrock model identifier |
| `--campaign-model-endpoint` | Model endpoint type (bedrock-runtime, strands-openai-responses) |
| `--campaign-model-arn` | Full ARN for the inference profile |
| `--force-agentcore-runtime-update` | Force redeploy of AgentCore Runtime |
| `--enable-spotify` | Enable Spotify validation integration |
| `--lambda-arch` | Lambda architecture (x86_64, arm64) |

### Environment Management

`samconfig.toml` manages per-environment parameters. Each environment has its own config section (e.g. `[prod]`, `[teleport-dev]`). New environments prompt for stack name, region, and stream URL on first deploy.

### Frontend Deployment

Frontend files are deployed automatically as part of `deploy.sh`:
1. S3 upload of `frontend/` contents
2. CloudFront cache invalidation

No separate frontend deploy step is needed.

---

## Configuration

### DynamoDB Config Table

The Config table stores runtime configuration under these keys:

| Key | Contents |
|-----|----------|
| `chart_generation` | Chart reset day/hour, campaign generation day/hour, freeze enabled |
| `top10_filters` | Regex patterns excluding promotional content from chart |
| `campaign_branding` | Visual identity for generated assets |
| `verification_sources` | Track validation provider settings |

### Branding

Stored under `campaign_branding`:

- Chart title
- Tagline
- 5 colours: primary, secondary, accent, background, text
- Logo reference

Managed via Admin UI → Settings.

### Chart Schedule

- **Reset day/hour**: When the chart week rolls over
- **Campaign generation day/hour**: When scheduled campaign drafts are generated
- **Freeze enabled**: Prevents chart recalculation during review period

### Campaign Model

Configured via SAM parameters, not the Config table:

| Parameter | Value |
|-----------|-------|
| `CampaignModelId` | `global.anthropic.claude-sonnet-4-6` |
| `CampaignModelEndpoint` | `bedrock-runtime` |
| `CampaignModelResourceArn` | `arn:aws:bedrock:us-west-2:ACCOUNT:inference-profile/global.anthropic.claude-sonnet-4-6` |

Pass these via `deploy.sh` flags or directly as `--parameter-overrides` in `sam deploy`.

---

## Project Structure

```
src/
├── poller/                  # Stream polling (Shoutcast v1/v2)
├── validator/               # Track validation (MusicBrainz/Spotify)
├── api/                     # REST API handler
├── campaign-generator/      # Triggers AgentCore Runtime
├── agentcore-runtime/       # Strands Agent routing
├── agentcore-tools/         # Campaign orchestration + rendering
├── infographic-renderer/    # chart-poster.js template + Playwright
├── playlist-generator/      # Spotify playlist integration
└── schedule-updater/        # Schedule sync

layers/
└── common/                  # Shared Python modules

frontend/                    # Static site (admin.html, index.html)

docs/
├── agentic/context/         # AI steering context files
└── *.md                     # Documentation
```

---

## Key Files

| File | Purpose |
|------|---------|
| `template.yaml` | SAM infrastructure definition |
| `layers/common/campaign_generation.py` | Claude prompt assembly and generation |
| `layers/common/agent_context.py` | Context file loading for agent prompts |
| `layers/common/campaign_store.py` | DynamoDB campaign CRUD operations |
| `layers/common/chart_brief.py` | Deterministic chart brief builder |
| `layers/common/agent_memory.py` | AgentCore Memory adapter |
| `src/infographic-renderer/chart-poster.js` | Infographic HTML/CSS template |

---

## Monitoring

### CloudWatch Logs

Each Lambda function has a dedicated log group:

```
/aws/lambda/{stack-name}-stream-poller
/aws/lambda/{stack-name}-track-validator
/aws/lambda/{stack-name}-api
/aws/lambda/{stack-name}-campaign-generator
/aws/lambda/{stack-name}-agentcore-runtime
/aws/lambda/{stack-name}-agentcore-tools
/aws/lambda/{stack-name}-infographic-renderer
```

### Tail Logs

```bash
sam logs -n StreamPollerFunction --stack-name teleport-dev-muddys-top-10 --tail
sam logs -n TrackValidatorFunction --stack-name teleport-dev-muddys-top-10 --tail
sam logs -n ApiFunction --stack-name teleport-dev-muddys-top-10 --tail
sam logs -n CampaignGeneratorFunction --stack-name teleport-dev-muddys-top-10 --tail
sam logs -n AgentCoreRuntimeFunction --stack-name teleport-dev-muddys-top-10 --tail
sam logs -n AgentCoreToolsFunction --stack-name teleport-dev-muddys-top-10 --tail
```

Replace `teleport-dev-muddys-top-10` with your stack name.
