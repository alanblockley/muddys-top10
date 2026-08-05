# Security Model

## Public Access

### Welcome Page (/)
- **URL**: `https://your-cloudfront-url/`
- **Content**: latest approved or published campaign PNG
- **Authentication not required**
- Reads only `GET /api/public/latest-campaign`, which returns public PNG metadata and a short-lived presigned image URL

## Authenticated Access

### Admin Panel (/admin.html)
- **URL**: `https://your-cloudfront-url/admin.html`
- **Requires**: Cognito authentication
- **Features**:
  - 📜 **History Tab**: View all tracks from last 7 days
  - 🎚️ **Filters Tab**: Manage Top 10 filter patterns
  - 📊 **Chart Config Tab**: Configure weekly chart generation time

### Protected API Endpoints
- `GET /api/top10` - Current Top 10 chart
- `GET /api/top10/history` - Weekly Top 10 snapshot index
- `GET /api/top10/history/{week_id}` - Weekly Top 10 snapshot detail
- `GET /api/config` - View current configuration
- `GET /api/health` - Health check
- `GET /api/history` - Requires JWT token in Authorization header
- `PUT /api/config` - Requires JWT token in Authorization header
- `GET /api/spotify/connect` - Starts Spotify OAuth for an authenticated admin
- `GET /api/spotify/status` - Checks Spotify connection status
- `POST /api/spotify/generate-playlist` - Manually generates playlist
- `POST /api/spotify/disconnect` - Disconnects Spotify
- `GET /api/campaigns` - Lists generated campaign drafts
- `GET /api/campaigns/{week_id}` - Reads one campaign draft
- `POST /api/campaigns/generate` - Human-triggered campaign generation/regeneration
- `PUT /api/campaigns/{week_id}` - Edits generated campaign content
- `PUT /api/campaigns/{week_id}/status` - Updates review/approval/published status

### Public API Endpoints
- `GET /api/public/latest-campaign` - Latest approved or published campaign PNG metadata only

### Technical Callback Endpoint
- `GET /api/spotify/callback` remains externally reachable so Spotify can complete OAuth.
- The callback only succeeds for a state created by an authenticated `/api/spotify/connect` request.
- Spotify playlist/OAuth access is controlled separately from Spotify track
  validation. `EnableSpotifyPlaylists=false` blocks Spotify admin actions, hides
  the Spotify playlist tab, and disables playlist scheduling. Spotify validation
  is controlled by `EnableSpotifyValidation` plus the admin `verification_sources`
  setting.

### Scheduled Agentic Workflow

- Weekly campaign draft generation runs outside Cognito user scope.
- EventBridge invokes `CampaignGeneratorFunction` using IAM.
- The scheduled workload reads chart history and writes campaign drafts with least-privilege table permissions.
- Draft records use `generated_by = scheduled-agent` and no `requested_by` user.
- Human review, approval, manual regeneration, and publishing status changes remain Cognito-authenticated.

### AgentCore Gateway Workflow

- AgentCore Gateway resources are required by the stack.
- Gateway inbound auth is IAM, not Cognito.
- The gateway invokes `AgentCoreToolsFunction` through a dedicated gateway service role.
- The gateway role is scoped to `lambda:InvokeFunction` for the AgentCore tool Lambda.
- Tool execution records `generated_by = agentcore` for generated campaign drafts.

### AgentCore Memory Workflow

- AgentCore Memory resources are required by the stack.
- Memory access uses Lambda execution-role IAM permissions, not Cognito user scope.
- Only `AgentCoreToolsFunction` can retrieve and write campaign memory.
- Memory is used for campaign editorial continuity, not as an authority for chart facts.
- Current chart facts still come from DynamoDB `top10_history` and generated `chart_brief` records.

## Authentication Flow

1. User visits `/` or `/admin.html`
2. Clicks "Sign In" button
3. Redirected to Cognito Hosted UI
4. Enters credentials (email + password)
5. On success, redirected back to the requested page with JWT token
6. Token stored in browser localStorage
7. All app API requests include token in Authorization header

## Token Management

- **Storage**: Browser localStorage
- **Lifetime**: 1 hour (Cognito default)
- **Refresh**: User must sign in again after expiration
- **Logout**: Clears token and redirects to Cognito logout

## User Management

Admin users must be created manually via AWS CLI or Console:

```bash
aws cognito-idp admin-create-user \
    --user-pool-id <pool-id> \
    --username admin@example.com \
    --user-attributes \
        Name=email,Value=admin@example.com \
        Name=email_verified,Value=true
```

See [COGNITO_SETUP.md](COGNITO_SETUP.md) for full user management guide.

## Security Features

### Password Policy
- Minimum 8 characters
- Requires uppercase letter
- Requires lowercase letter
- Requires number
- Symbols optional

### API Gateway Authorization
- Cognito authorizer validates JWT tokens
- Invalid/expired tokens return 401 Unauthorized
- App endpoints require authorization

### CORS Configuration
- Allows all origins
- Allows the Authorization header required by protected endpoints

## Implementation Details

### Frontend
- **index.html**: Public welcome page with latest approved or published campaign PNG
- **admin.html**: Full authenticated admin interface

### API Lambda
- API Gateway handles Cognito authorization before requests reach the Lambda
- Spotify OAuth connect can return a JSON authorization URL for authenticated browser fetches

### CloudFormation
- Cognito User Pool with email verification
- User Pool Client with OAuth2/Hosted UI
- API Gateway Cognito Authorizer
- Authorizer applied to all app endpoints

## Why This Model?

**Protected Top 10 and History**:
- Prevents abuse/scraping of full data
- Limits access to detailed track history
- Admin-only feature

**Protected Config**:
- Prevents unauthorized changes to filters
- Prevents unauthorized changes to chart timing
- Ensures data integrity

## Future Enhancements

Potential improvements:
- Add user roles (admin vs viewer)
- Enable self-service signup with email verification
- Add MFA for admin accounts
- Add rate limiting on API endpoints
- Add API keys for programmatic access
- Add audit logging for config changes
