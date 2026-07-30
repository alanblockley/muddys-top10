# Documentation Index

This folder is the canonical home for project documentation. The root `README.md` remains the high-level project overview; detailed current-state, operational, reference, future-state, and historical docs live here.

## Current System

- [ARCHITECTURE.md](ARCHITECTURE.md) - Current AWS/SAM architecture, data flow, and access patterns.
- [SECURITY_MODEL.md](SECURITY_MODEL.md) - Current Cognito-authenticated access model.
- [COGNITO_SETUP.md](COGNITO_SETUP.md) - Creating and managing Cognito users.
- [STREAM_FORMATS.md](STREAM_FORMATS.md) - Supported Shoutcast metadata formats.
- [TRACK_VALIDATION.md](TRACK_VALIDATION.md) - Current validation and canonicalization system.
- [CLEAN_TITLES.MD](CLEAN_TITLES.MD) - Title cleaning rules.
- [FILTERS.md](FILTERS.md) - Banned-song/top-10 filter management.
- [SOCIAL_MEDIA_EXPORT.md](SOCIAL_MEDIA_EXPORT.md) - Current browser-side infographic export feature.
- [LISTENER_GUIDE.md](LISTENER_GUIDE.md) - Listener-facing explanation of the Top 10.

## Deployment And Operations

- [QUICKSTART.md](QUICKSTART.md) - Fast deployment/startup guide.
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide and environment notes.
- [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) - Deployment checklist.
- [DEPLOY_SCRIPT_EXPLAINED.md](DEPLOY_SCRIPT_EXPLAINED.md) - Current `deploy.sh` flow.
- [BACKFILL_GUIDE.md](BACKFILL_GUIDE.md) - Data maintenance, export/import, backfill, and cleanup tools.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Operational troubleshooting.
- [review-cli/README.md](../review-cli/README.md) - Rust CLI for authenticated, read-only API data review.

## Spotify

- [SPOTIFY_PLAYLIST_SETUP.md](SPOTIFY_PLAYLIST_SETUP.md) - Recommended admin-panel Spotify setup.
- [SPOTIFY_PLAYLIST_SETUP_CLI.md](SPOTIFY_PLAYLIST_SETUP_CLI.md) - Older command-line Spotify setup fallback.
- [SPOTIFY_API_CALLS.md](SPOTIFY_API_CALLS.md) - Spotify API endpoint reference.

## Reference

- [track_validation_logic.md](track_validation_logic.md) - Detailed validation/scoring logic.

## Future State

- [AGENTCORE_CAMPAIGN_REQUIREMENTS.md](AGENTCORE_CAMPAIGN_REQUIREMENTS.md) - Planned AgentCore/MCP chart campaign generation requirements.
- [agentic/README.md](agentic/README.md) - Agentic workflow journey, context packs, output contracts, review workflow, and roadmap.
- [agent-spec/01a-Infographic-Agent-v3.md](agent-spec/01a-Infographic-Agent-v3.md) - Authoritative infographic editorial production-agent spec.
- [agent-spec/01b-Generate-Infographic-Asset.md](agent-spec/01b-Generate-Infographic-Asset.md) - Deterministic final infographic asset renderer spec.
- [../infographic-renderer/README.md](../infographic-renderer/README.md) - Standalone HTML/CSS/SVG plus Playwright renderer for final PNG assets.
- [agent-spec/02-Social-Agent-v3.md](agent-spec/02-Social-Agent-v3.md) - Authoritative social media production-agent spec.
- [agent-spec/03-Radio-Agent-v3.md](agent-spec/03-Radio-Agent-v3.md) - Authoritative radio reads production-agent spec.

## Historical / Archive

These documents are retained for context but may describe implementation history rather than current behavior.

- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Track validation implementation notes.
- [PROJECT_SUMMARY.txt](PROJECT_SUMMARY.txt) - Historical project summary.
- [archive/MANUAL_PLAYLIST_FEATURE.md](archive/MANUAL_PLAYLIST_FEATURE.md) - Manual playlist generation feature notes.
- [archive/SPOTIFY_OAUTH_DEPLOYMENT.md](archive/SPOTIFY_OAUTH_DEPLOYMENT.md) - Historical Spotify OAuth deployment notes.
