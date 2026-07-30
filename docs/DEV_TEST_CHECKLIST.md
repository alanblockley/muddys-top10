# Dev Test Checklist

Use this checklist after deploying to `teleport-dev`.

## Deploy Smoke

- [x] Run `./deploy.sh --env teleport-dev --disable-spotify-playlists --enable-spotify-validation`.
- [x] Confirm the deploy completes successfully.
- [x] Confirm frontend files upload successfully.
- [x] Open the admin page.
- [x] Confirm Cognito login works.
- [x] Confirm the Spotify tab is not visible when disabled.
- [x] Open the Top 10 page.
- [x] Confirm the Top 10 page loads behind auth.
- [x] Confirm history still loads behind auth.

## Spotify Playlists Disabled

- [ ] Call `GET /api/spotify/status` with auth.
- [ ] Confirm the response includes `"enabled": false`.
- [ ] Confirm the response includes `"connected": false`.
- [ ] Call `GET /api/spotify/connect` with auth.
- [ ] Confirm the response is HTTP `403`.
- [ ] Call `POST /api/spotify/generate-playlist` with auth.
- [ ] Confirm the response is HTTP `403`.
- [ ] Call `POST /api/spotify/disconnect` with auth.
- [ ] Confirm the response is HTTP `403`.
- [ ] Open Admin → Settings.
- [ ] Confirm Spotify validation can remain enabled independently of playlist generation.
- [ ] Check CloudWatch logs for `teleport-dev-muddys-top-10-track-validator`.
- [ ] Confirm validator logs reflect the Admin verification source settings.
- [ ] Check the EventBridge playlist schedule.
- [ ] Confirm the playlist generator rule is disabled.

## Spotify Playlists Enabled

- [ ] Run `./deploy.sh --env teleport-dev --enable-spotify-playlists`.
- [ ] Confirm the deploy completes successfully.
- [ ] Open the admin page.
- [ ] Confirm the Spotify tab is visible.
- [ ] Call `GET /api/spotify/status` with auth.
- [ ] Confirm the response includes `"enabled": true`.
- [ ] If no refresh token exists, confirm the response includes `"connected": false`.
- [ ] Click `Connect Spotify Account`.
- [ ] Confirm the browser redirects to Spotify OAuth.
- [ ] Complete Spotify OAuth.
- [ ] Confirm the admin page shows Spotify as connected.
- [ ] Trigger manual playlist generation.
- [ ] Confirm a playlist is created, or a clear credential/token error is shown.
- [ ] Check the EventBridge playlist schedule.
- [ ] Confirm the playlist generator rule is enabled.

## Campaign UI

- [x] Open the admin Campaigns tab.
- [x] Click `Refresh Campaigns`.
- [x] Confirm existing campaign drafts load.
- [x] Generate a campaign draft with no week id.
- [x] Confirm a draft is created for the latest available chart snapshot.
- [x] Generate a campaign draft for a known historical week id.
- [x] Confirm the historical draft opens correctly.
- [x] Confirm the chart snapshot preview shows 10 tracks.
- [x] Confirm DJ readout preview renders.
- [x] Confirm infographic preview renders.
- [x] Confirm social copy preview renders.
- [x] Edit one JSON section.
- [x] Save edited content.
- [x] Reload the campaign.
- [x] Confirm the edit persisted.
- [x] Mark the campaign as `reviewed`.
- [x] Confirm status changes to `reviewed`.
- [x] Mark the campaign as `approved`.
- [x] Confirm status changes to `approved`.
- [x] Mark the campaign as `published`.
- [x] Confirm status changes to `published`.

## AgentCore Routing

- [ ] Generate a campaign from the admin UI.
- [ ] Check CloudWatch logs for `teleport-dev-muddys-top-10-api`.
- [ ] Confirm the API Lambda invokes `teleport-dev-muddys-top-10-agentcore-tools`.
- [ ] Confirm the API Lambda does not directly call Bedrock.
- [ ] Check CloudWatch logs for `teleport-dev-muddys-top-10-agentcore-tools`.
- [ ] Confirm campaign generation happens in the AgentCore tools Lambda.
- [ ] Confirm model-backed generation logs appear only in the AgentCore tools Lambda.
- [ ] Check CloudWatch logs for `teleport-dev-muddys-top-10-campaign-generator`.
- [ ] Manually invoke the scheduled campaign generator Lambda if needed.
- [ ] Confirm it invokes `teleport-dev-muddys-top-10-agentcore-tools`.
- [ ] Confirm it does not directly call Bedrock.

## Campaign Temporal Regression

- [ ] Generate a campaign for a historical week, for example `2026-05-09`.
- [ ] Inspect `weeks_on_chart` values.
- [ ] Confirm values do not include future weeks.
- [ ] Inspect movement and previous rank fields.
- [ ] Confirm movement only uses chart snapshots before the requested week.
- [ ] Compare the campaign chart brief with `/api/top10/history/YYYY-MM-DD`.
- [ ] Confirm the campaign uses the same week snapshot.

## Core API Regression

- [ ] Call `GET /api/top10` with auth.
- [ ] Confirm it returns the current Top 10.
- [ ] Call `GET /api/history` with auth.
- [ ] Confirm it returns recent track history.
- [ ] Call `GET /api/top10/history` with auth.
- [ ] Confirm it returns the available week index.
- [ ] Call `GET /api/top10/history/YYYY-MM-DD` with auth.
- [ ] Confirm it returns that week snapshot.
- [ ] Call `GET /api/config` with auth.
- [ ] Confirm config loads.
- [ ] Save Top 10 filters from admin.
- [ ] Confirm filters persist after reload.
- [ ] Save chart generation config from admin.
- [ ] Confirm chart config persists after reload.
- [ ] Confirm unauthenticated API calls are rejected.

## Data Processing Regression

- [ ] Confirm the poller is still running on schedule.
- [ ] Confirm new track records are written to DynamoDB.
- [ ] Confirm validator processes new track records.
- [ ] Confirm validation still works when Spotify playlist generation is disabled.
- [ ] Confirm validation can use Spotify when Spotify validation is enabled and credentials exist.
- [ ] Confirm Top 10 filters still exclude banned/promotional tracks from chart output.
