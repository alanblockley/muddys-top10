# Documentation

## Core Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, component diagram, data flows |
| [TECHNICAL.md](TECHNICAL.md) | Deployment, configuration, project structure, monitoring |
| [USER_GUIDE.md](USER_GUIDE.md) | Admin UI guide for non-technical users |
| [CHANGELOG.md](CHANGELOG.md) | All notable changes to the system |

## Operational Guides

| Document | Description |
|----------|-------------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Detailed deployment instructions and parameters |
| [COGNITO_SETUP.md](COGNITO_SETUP.md) | User pool management, creating admin users |
| [BACKFILL_GUIDE.md](BACKFILL_GUIDE.md) | DynamoDB data export/import, history backfill |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and debugging |
| [SECURITY_MODEL.md](SECURITY_MODEL.md) | Authentication, authorization, IAM policies |

## Feature Documentation

| Document | Description |
|----------|-------------|
| [TRACK_VALIDATION.md](TRACK_VALIDATION.md) | MusicBrainz/Spotify validation system |
| [STREAM_FORMATS.md](STREAM_FORMATS.md) | Shoutcast v1/v2 format detection |
| [FILTERS.md](FILTERS.md) | Top 10 regex filter patterns |
| [LISTENER_GUIDE.md](LISTENER_GUIDE.md) | How the chart works (for listeners/DJs) |
| [SPOTIFY_API_CALLS.md](SPOTIFY_API_CALLS.md) | Spotify API integration details |
| [SPOTIFY_PLAYLIST_SETUP.md](SPOTIFY_PLAYLIST_SETUP.md) | Spotify playlist configuration |
| [INFOGRAPHIC_TEMPLATE.md](INFOGRAPHIC_TEMPLATE.md) | How to modify the chart PNG template |

## AI Context Files

Located in `agentic/context/` — these are loaded by the campaign generation system to steer Claude's output:

| File | Purpose |
|------|---------|
| `infographic-editorial-framework.md` | Chart Talk editorial categories and rules |
| `personal-voice.md` | Alan's writing tone and style |
| `muddys-venue-context.md` | Venue, community, Second Life context |
| `radio-chart-show-convention.md` | Movement language and narrative conventions |
| `chart-show-glossary.md` | Chart terminology |
| `radio-read-examples.md` | Golden examples of radio read copy |
| `social-style-examples.md` | Social post examples by platform |
| `social-media-music-communities.md` | Community engagement patterns |
| `words-and-phrases.md` | Preferred vocabulary |
| `never-say.md` | Banned words and framing |

## Archive

Historical documents (planning, superseded specs, migration notes) are in `archive/`.
