# `review-cli`

Read-only Rust CLI for inspecting data exposed by the Muddy's Top 10 API.

It does not talk to DynamoDB directly and does not modify the existing stack. It only calls the API endpoints that already exist and adds one local aggregation command over `/api/history`.

## Commands

- `setup`: create or update the local CLI config file
- `login`: sign in via Cognito Hosted UI and save a bearer token locally
- `console`: open an interactive prompt and issue commands in-session
- `profile`: show the local CLI config path and whether settings are present
- `health`: call `/api/health` (requires token)
- `top10`: call `/api/top10` (requires token)
- `top10-history`: call `/api/top10/history` and list persisted weekly chart snapshots (requires token)
- `top10-history-week`: call `/api/top10/history/YYYY-MM-DD` and show one persisted chart snapshot (requires token)
- `config`: call `/api/config` (requires token)
- `spotify-status`: call `/api/spotify/status` (requires token)
- `campaigns`: call `/api/campaigns` and list generated campaign drafts (requires token)
- `campaign`: call `/api/campaigns/YYYY-MM-DD` and summarize one campaign draft (requires token)
- `campaign-generate`: call `/api/campaigns/generate` to generate or regenerate a campaign draft from persisted history (requires token)
- `history`: call `/api/history` and print recent grouped or flat history (requires token)
- `top`: compute top tracks for the last `N` days from `/api/history` (requires token)
- `top`: by default applies the same `top10_filters` rules used by the app's weekly Top 10; use `--no-chart-rules` to disable that
- `stats`: compute summary counts for the last `N` days from `/api/history` (requires token)

## Usage

```bash
cargo run -- --profile dev setup \
  --stack-name teleport-dev-muddys-top-10 \
  --region us-west-2 \
  --cognito-redirect-uri http://localhost:0/admin.html

cargo run -- --profile prod setup \
  --stack-name teleport-prod-muddys-top-10 \
  --region us-west-2 \
  --cognito-redirect-uri http://localhost:8000/admin.html

# Use port 0 to bind a random available local callback port.
cargo run -- --profile prod setup \
  --stack-name teleport-prod-muddys-top-10 \
  --cognito-redirect-uri http://localhost:0/admin.html

cargo run -- --profile dev login

cargo run -- --profile dev console

cargo run -- --profile dev health

cargo run -- --profile dev top10

cargo run -- --profile dev top10-history --limit 12

cargo run -- --profile dev top10-history --from 2026-07-01 --to 2026-07-31 --detail

cargo run -- --profile dev top10-history-week 2026-07-18

cargo run -- --profile dev campaigns --limit 20

cargo run -- --profile dev campaign 2026-07-20

cargo run -- --profile dev campaign-generate --week-id 2026-07-20 --sections radio,social

cargo run -- --profile dev history --days 2 --flat --limit 50

cargo run -- --profile dev top --days 7 --limit 20

cargo run -- --profile dev top --days 7 --limit 20 --no-chart-rules
```

API commands automatically trigger `login` if no usable bearer token is stored.

## Console Mode

Run:

```bash
cargo run -- console
```

Then type commands directly:

```text
review-cli> top10
review-cli> top10-history --limit 12
review-cli> top10-history-week 2026-07-18
review-cli> history --days 2 --flat --limit 25
review-cli> top --days 7 --limit 15
review-cli> campaigns
review-cli> campaign 2026-07-20
review-cli> campaign-generate --week-id 2026-07-20 --sections radio
review-cli> profile
review-cli> profile --profile prod
review-cli> exit
```

`help`, `exit`, and `quit` are supported inside the console.

Flags still override the stored config for a single invocation:

```bash
cargo run -- --api-base https://other-host top10

cargo run -- --token "$OTHER_JWT" history --days 1
```

You can also use environment variables:

```bash
export MUDDYS_API_BASE=https://your-api-host
export MUDDYS_API_TOKEN=your-jwt-token
export MUDDYS_CONFIG_PATH=/custom/path/review-cli.json
export MUDDYS_PROFILE=dev

cargo run -- top10
cargo run -- history --days 1
```

If you run `cargo run -- setup` without arguments, it will prompt for missing values.

## Hosted UI Login

`login` uses the same implicit Hosted UI flow as the admin frontend:

1. The CLI starts a local callback listener on the configured redirect URI. If the configured port is `0`, the CLI asks the OS for a random available port and sends that resolved callback URI to Cognito.
2. It prints the Cognito login URL.
3. You open that URL in a browser and sign in with your Cognito credentials.
4. Cognito redirects to the local callback URI, such as `http://localhost:8000/admin.html#id_token=...` or the resolved random port when `:0` is configured.
5. The CLI captures the token and stores it in the local config file.

This works without changing the existing AWS stack because the repo already documents localhost callback support.

## Output

Default output is table-formatted. Use `--output json` for machine-readable output.

```bash
cargo run -- --output json top10
```

## Notes

- `history`, `top`, and `stats` are limited to `1..=7` days because the API only exposes the last 7 days of history.
- `top` now applies the configured Top 10 filter rules by default so its output lines up more closely with the app's chart logic.
- `top10-history` reads persisted chart facts only. Campaign copy remains under `campaigns` / `campaign-generate`.
- `campaign-generate` uses official persisted `top10_history`; it is not for current unfinished chart testing.
- `setup` writes a JSON config file to `$XDG_CONFIG_HOME/review-cli/config.json` by default, or `~/.config/review-cli/config.json` when `XDG_CONFIG_HOME` is not set.
- `setup --stack-name STACK --region REGION` reads `ApiUrl`, `UserPoolClientId`, and `CognitoHostedUIUrl` from CloudFormation outputs.
- `--api-base` accepts either the site origin (`https://host`) or an API root (`https://host/api`).
- Use `--profile dev` / `--profile prod` or `MUDDYS_PROFILE` to switch saved API/Cognito/token settings.
- Existing single-profile config files are still read as the `default` profile.
- Stored config precedence is: command-line flags, then environment variables, then the selected saved profile.
- Stored per-profile Cognito settings are: `cognito_client_id`, `cognito_domain`, and `cognito_redirect_uri`.
