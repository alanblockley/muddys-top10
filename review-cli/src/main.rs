mod api;
mod auth;
mod local_config;
mod models;

use std::collections::{BTreeMap, HashMap, HashSet};
use std::io::{self, Write};
use std::path::Path;
use std::process::Command as ProcessCommand;

use anyhow::{Context, Result, bail};
use base64::Engine;
use chrono::Utc;
use clap::{Parser, Subcommand, ValueEnum};
use comfy_table::{Cell, ContentArrangement, Table, presets::UTF8_FULL};
use local_config::{
    ProfileConfig, StoredConfig, load_config, prompt, resolve_config_path, save_config,
};
use models::{
    CampaignGenerateResponse, CampaignResponse, CampaignsResponse, ConfigResponse, HealthResponse,
    HistoryResponse, HistoryTrack, ScheduleConfig, StatsSummary, StatusCount, Top10HistoryResponse,
    Top10HistoryWeekResponse, Top10Response, TopAggregateRow,
};
use serde::Deserialize;

use crate::api::ApiClient;

#[derive(Debug, Parser)]
#[command(author, version, about = "Read-only CLI for the Muddy's Top 10 API")]
struct Cli {
    #[arg(long, env = "MUDDYS_API_BASE")]
    api_base: Option<String>,

    #[arg(long, env = "MUDDYS_API_TOKEN")]
    token: Option<String>,

    #[arg(long, env = "MUDDYS_CONFIG_PATH")]
    config: Option<String>,

    #[arg(long, global = true, env = "MUDDYS_PROFILE")]
    profile: Option<String>,

    #[arg(long, value_enum, default_value_t = OutputFormat::Table)]
    output: OutputFormat,

    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum OutputFormat {
    Table,
    Json,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Create or update the local CLI config file.
    Setup {
        #[arg(long)]
        stack_name: Option<String>,

        #[arg(long)]
        region: Option<String>,

        #[arg(long)]
        api_base: Option<String>,

        #[arg(long)]
        token: Option<String>,

        #[arg(long)]
        cognito_client_id: Option<String>,

        #[arg(long)]
        cognito_domain: Option<String>,

        #[arg(long)]
        cognito_redirect_uri: Option<String>,

        #[arg(long)]
        clear_token: bool,

        #[arg(long)]
        no_prompt: bool,
    },
    /// Show the local CLI config and where it is stored.
    Profile,
    /// Sign in through Cognito Hosted UI and save a bearer token locally.
    Login,
    /// Open an interactive console and run commands in a session.
    Console,
    /// Check API health.
    Health,
    /// Show the server-generated weekly top 10.
    Top10,
    /// List persisted weekly Top 10 history snapshots.
    Top10History {
        #[arg(long, default_value_t = 12)]
        limit: usize,

        #[arg(long)]
        from: Option<String>,

        #[arg(long)]
        to: Option<String>,

        #[arg(long)]
        detail: bool,

        #[arg(long)]
        all: bool,
    },
    /// Show one persisted weekly Top 10 history snapshot.
    Top10HistoryWeek { week_id: String },
    /// Show current configuration.
    Config,
    /// Show Spotify connection status.
    SpotifyStatus,
    /// List generated campaign drafts.
    Campaigns {
        #[arg(long, default_value_t = 20)]
        limit: usize,
    },
    /// Show one campaign draft by week id.
    Campaign { week_id: String },
    /// Generate or regenerate a campaign draft from persisted Top 10 history.
    CampaignGenerate {
        #[arg(long)]
        week_id: Option<String>,

        #[arg(long)]
        sections: Option<String>,
    },
    /// Show track history from the protected history endpoint.
    History {
        #[arg(long, default_value_t = 1)]
        days: u32,

        #[arg(long)]
        flat: bool,

        #[arg(long)]
        limit: Option<usize>,
    },
    /// Compute top tracks over the last N days from history data.
    Top {
        #[arg(long, default_value_t = 7)]
        days: u32,

        #[arg(long, default_value_t = 10)]
        limit: usize,

        #[arg(long)]
        raw: bool,

        #[arg(long)]
        no_chart_rules: bool,
    },
    /// Show summary counts over the last N days from history data.
    Stats {
        #[arg(long, default_value_t = 7)]
        days: u32,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let config_path = resolve_config_path(cli.config.as_deref())?;
    let mut stored = load_config(&config_path)?;
    let profile_name = stored.profile_name(cli.profile.as_deref());
    execute_command(&cli, &config_path, &profile_name, &mut stored)
}

fn execute_command(
    cli: &Cli,
    config_path: &Path,
    profile_name: &str,
    stored: &mut StoredConfig,
) -> Result<()> {
    match &cli.command {
        Command::Setup {
            stack_name,
            region,
            api_base,
            token,
            cognito_client_id,
            cognito_domain,
            cognito_redirect_uri,
            clear_token,
            no_prompt,
        } => run_setup(
            config_path,
            profile_name,
            stored,
            stack_name.clone(),
            region.clone(),
            api_base.clone(),
            token.clone(),
            cognito_client_id.clone(),
            cognito_domain.clone(),
            cognito_redirect_uri.clone(),
            *clear_token,
            *no_prompt,
        ),
        Command::Profile => render_profile(
            cli.output,
            config_path,
            profile_name,
            &stored.profile(profile_name),
            stored,
        ),
        Command::Login => {
            let mut profile = stored.profile(profile_name);
            auth::perform_hosted_ui_login(config_path, &mut profile)?;
            stored.set_profile(profile_name, profile);
            save_config(config_path, stored)?;
            println!(
                "Saved profile `{profile_name}` to {}",
                config_path.display()
            );
            Ok(())
        }
        Command::Console => run_console(cli, config_path, profile_name, stored),
        Command::Health => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            render_health(cli.output, api.health()?)
        }
        Command::Top10 => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            render_top10(cli.output, api.top10()?)
        }
        Command::Top10History {
            limit,
            from,
            to,
            detail,
            all,
        } => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            render_top10_history(
                cli.output,
                api.top10_history(*limit, from.as_deref(), to.as_deref(), *detail, *all)?,
            )
        }
        Command::Top10HistoryWeek { week_id } => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            render_top10_history_week(cli.output, api.top10_history_week(week_id)?)
        }
        Command::Config => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            render_config(cli.output, api.config()?)
        }
        Command::SpotifyStatus => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            render_spotify_status(cli.output, api.spotify_status()?)
        }
        Command::Campaigns { limit } => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            render_campaigns(cli.output, api.campaigns(*limit)?)
        }
        Command::Campaign { week_id } => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            render_campaign(cli.output, api.campaign(week_id)?)
        }
        Command::CampaignGenerate { week_id, sections } => {
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            let sections = parse_sections_arg(sections.as_deref())?;
            render_campaign_generate(
                cli.output,
                api.generate_campaign(week_id.as_deref(), sections.as_deref())?,
            )
        }
        Command::History { days, flat, limit } => {
            validate_history_days(*days)?;
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            let history = api.history()?;
            let tracks = filter_tracks_by_days(&history, *days);
            render_history(cli.output, *days, *flat, *limit, &history, &tracks)
        }
        Command::Top {
            days,
            limit,
            raw,
            no_chart_rules,
        } => {
            validate_history_days(*days)?;
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            let history = api.history()?;
            let tracks = filter_tracks_by_days(&history, *days);
            let chart_filter = if *no_chart_rules {
                None
            } else {
                Some(build_chart_filter(api.config()?.top10_filters))
            };
            let rows = aggregate_top_tracks(&tracks, *limit, *raw, chart_filter.as_ref());
            render_top_aggregate(cli.output, *days, *raw, !*no_chart_rules, rows)
        }
        Command::Stats { days } => {
            validate_history_days(*days)?;
            let api = api_client_from_sources(cli, config_path, profile_name, stored, true)?;
            let history = api.history()?;
            let tracks = filter_tracks_by_days(&history, *days);
            let summary = summarize_tracks(*days, &tracks);
            render_stats(cli.output, summary)
        }
    }
}

fn run_console(
    cli: &Cli,
    config_path: &Path,
    profile_name: &str,
    stored: &mut StoredConfig,
) -> Result<()> {
    println!("Interactive console mode");
    println!("Profile: {profile_name}");
    println!("Type commands such as `top10`, `history --days 2`, `top --days 7`.");
    println!("Use `help` to show commands and `exit` or `quit` to leave.");

    let mut input = String::new();
    loop {
        print!("review-cli> ");
        io::stdout().flush()?;

        input.clear();
        let bytes = io::stdin().read_line(&mut input)?;
        if bytes == 0 {
            println!();
            break;
        }

        let line = input.trim();
        if line.is_empty() {
            continue;
        }
        if matches!(line, "exit" | "quit") {
            break;
        }
        if line == "help" {
            print_console_help();
            continue;
        }

        match parse_console_cli(cli, config_path, line) {
            Ok(console_cli) => {
                let console_profile_name = stored.profile_name(console_cli.profile.as_deref());
                if let Err(error) =
                    execute_command(&console_cli, config_path, &console_profile_name, stored)
                {
                    eprintln!("error: {error:#}");
                }
            }
            Err(error) => {
                eprintln!("error: {error}");
            }
        }
    }

    Ok(())
}

fn parse_console_cli(cli: &Cli, config_path: &Path, line: &str) -> Result<Cli> {
    let mut args = vec!["review-cli".to_string()];
    if let Some(api_base) = &cli.api_base {
        args.push("--api-base".to_string());
        args.push(api_base.clone());
    }
    if let Some(token) = &cli.token {
        args.push("--token".to_string());
        args.push(token.clone());
    }
    args.push("--config".to_string());
    args.push(config_path.display().to_string());
    if let Some(profile) = &cli.profile {
        args.push("--profile".to_string());
        args.push(profile.clone());
    }
    args.push("--output".to_string());
    args.push(match cli.output {
        OutputFormat::Table => "table".to_string(),
        OutputFormat::Json => "json".to_string(),
    });
    args.extend(shell_words::split(line).context("failed to parse console input")?);
    Cli::try_parse_from(args).map_err(|error| anyhow::anyhow!(error.to_string()))
}

fn print_console_help() {
    println!("Commands:");
    println!("  health");
    println!("  top10");
    println!(
        "  top10-history [--limit N] [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--detail] [--all]"
    );
    println!("  top10-history-week YYYY-MM-DD");
    println!("  config");
    println!("  campaigns [--limit N]");
    println!("  campaign YYYY-MM-DD");
    println!("  campaign-generate [--week-id YYYY-MM-DD] [--sections radio,infographic,social]");
    println!("  profile");
    println!("  profile --profile dev");
    println!("  login");
    println!("  history --days N [--flat] [--limit N]");
    println!("  top --days N --limit N [--raw] [--no-chart-rules]");
    println!("  stats --days N");
    println!("  setup [--api-base URL] [--cognito-client-id ID] [--cognito-domain URL]");
    println!("  setup --profile dev --api-base URL --cognito-client-id ID --cognito-domain URL");
    println!("  exit");
}

fn api_client_from_sources(
    cli: &Cli,
    config_path: &Path,
    profile_name: &str,
    stored: &mut StoredConfig,
    requires_auth: bool,
) -> Result<ApiClient> {
    let mut profile = stored.profile(profile_name);
    let api_base = cli
        .api_base
        .clone()
        .or_else(|| profile.api_base.clone())
        .with_context(|| {
            format!("API base is not configured for profile `{profile_name}`; run `review-cli --profile {profile_name} setup` or pass --api-base")
        })?;
    let token = if cli.token.is_some() {
        cli.token.clone()
    } else if requires_auth {
        let token = resolve_or_login_token(config_path, profile_name, &mut profile)?;
        stored.set_profile(profile_name, profile);
        save_config(config_path, stored)?;
        token
    } else {
        profile
            .token
            .clone()
            .filter(|token| !token.is_empty() && !token_expired(token))
    };
    ApiClient::new(&api_base, token)
}

fn resolve_or_login_token(
    config_path: &Path,
    profile_name: &str,
    profile: &mut ProfileConfig,
) -> Result<Option<String>> {
    if let Some(token) = profile.token.clone() {
        if !token.is_empty() && !token_expired(&token) {
            return Ok(Some(token));
        }
    }

    println!("No valid token for profile `{profile_name}`; starting Cognito login.");
    let token = auth::perform_hosted_ui_login(config_path, profile)?;
    Ok(Some(token))
}

fn run_setup(
    config_path: &Path,
    profile_name: &str,
    stored: &mut StoredConfig,
    stack_name: Option<String>,
    region: Option<String>,
    api_base: Option<String>,
    token: Option<String>,
    cognito_client_id: Option<String>,
    cognito_domain: Option<String>,
    cognito_redirect_uri: Option<String>,
    clear_token: bool,
    no_prompt: bool,
) -> Result<()> {
    let current = stored.profile(profile_name);
    let resolved_stack_name = stack_name.or(current.stack_name.clone());
    let resolved_region = region.or(current.region.clone());
    let stack_defaults = if let Some(stack_name) = resolved_stack_name.as_deref() {
        Some(load_stack_profile_defaults(
            stack_name,
            resolved_region.as_deref(),
        )?)
    } else {
        None
    };

    let resolved_api_base = match api_base {
        Some(value) => value,
        None if stack_defaults
            .as_ref()
            .and_then(|item| item.api_base.as_ref())
            .is_some() =>
        {
            stack_defaults
                .as_ref()
                .and_then(|item| item.api_base.clone())
                .unwrap()
        }
        None if no_prompt => current
            .api_base
            .clone()
            .context("missing --api-base and no existing configured api_base")?,
        None => prompt("API base URL", current.api_base.as_deref())?,
    };

    if resolved_api_base.trim().is_empty() {
        bail!("api_base cannot be empty");
    }

    let resolved_token = if clear_token {
        None
    } else if let Some(value) = token {
        if value.trim().is_empty() {
            None
        } else {
            Some(value)
        }
    } else if no_prompt {
        current.token.clone()
    } else {
        let token_input = prompt(
            "Bearer token (leave blank to keep current, use --clear-token to remove)",
            None,
        )?;
        if token_input.is_empty() {
            current.token.clone()
        } else {
            Some(token_input)
        }
    };

    let resolved_cognito_client_id = match cognito_client_id {
        Some(value) => blank_to_none(value),
        None if stack_defaults
            .as_ref()
            .and_then(|item| item.cognito_client_id.as_ref())
            .is_some() =>
        {
            stack_defaults
                .as_ref()
                .and_then(|item| item.cognito_client_id.clone())
        }
        None if no_prompt => current.cognito_client_id.clone(),
        None => {
            let input = prompt("Cognito client ID", current.cognito_client_id.as_deref())?;
            blank_to_none(input)
        }
    };

    let resolved_cognito_domain = match cognito_domain {
        Some(value) => blank_to_none(value),
        None if stack_defaults
            .as_ref()
            .and_then(|item| item.cognito_domain.as_ref())
            .is_some() =>
        {
            stack_defaults
                .as_ref()
                .and_then(|item| item.cognito_domain.clone())
        }
        None if no_prompt => current.cognito_domain.clone(),
        None => {
            let input = prompt(
                "Cognito Hosted UI domain",
                current.cognito_domain.as_deref(),
            )?;
            blank_to_none(input)
        }
    };

    let redirect_default = current
        .cognito_redirect_uri
        .as_deref()
        .unwrap_or("http://localhost:8000/admin.html");
    let resolved_cognito_redirect_uri = match cognito_redirect_uri {
        Some(value) => blank_to_none(value),
        None if no_prompt => current
            .cognito_redirect_uri
            .clone()
            .or_else(|| Some("http://localhost:8000/admin.html".to_string())),
        None => {
            let input = prompt("Cognito redirect URI", Some(redirect_default))?;
            blank_to_none(input)
        }
    };

    let next = StoredConfig {
        stack_name: resolved_stack_name,
        region: resolved_region,
        api_base: Some(resolved_api_base),
        token: resolved_token,
        cognito_client_id: resolved_cognito_client_id,
        cognito_domain: resolved_cognito_domain,
        cognito_redirect_uri: resolved_cognito_redirect_uri,
        active_profile: None,
        profiles: BTreeMap::new(),
    };
    let profile = ProfileConfig {
        stack_name: next.stack_name,
        region: next.region,
        api_base: next.api_base,
        token: next.token,
        cognito_client_id: next.cognito_client_id,
        cognito_domain: next.cognito_domain,
        cognito_redirect_uri: next.cognito_redirect_uri,
    };
    stored.set_profile(profile_name, profile);
    save_config(config_path, stored)?;

    println!(
        "Saved CLI profile `{profile_name}` to {}",
        config_path.display()
    );
    Ok(())
}

#[derive(Debug)]
struct StackProfileDefaults {
    api_base: Option<String>,
    cognito_client_id: Option<String>,
    cognito_domain: Option<String>,
}

#[derive(Debug, Deserialize)]
struct StackOutput {
    #[serde(rename = "OutputKey")]
    key: String,
    #[serde(rename = "OutputValue")]
    value: String,
}

fn load_stack_profile_defaults(
    stack_name: &str,
    region: Option<&str>,
) -> Result<StackProfileDefaults> {
    let mut command = ProcessCommand::new("aws");
    command.args([
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        stack_name,
        "--query",
        "Stacks[0].Outputs",
        "--output",
        "json",
    ]);
    if let Some(region) = region {
        if !region.trim().is_empty() {
            command.args(["--region", region]);
        }
    }

    let output = command.output().context("failed to execute aws CLI")?;
    if !output.status.success() {
        bail!(
            "failed to read CloudFormation outputs for stack `{}`: {}",
            stack_name,
            String::from_utf8_lossy(&output.stderr).trim()
        );
    }

    let outputs: Vec<StackOutput> = serde_json::from_slice(&output.stdout)
        .context("failed to parse CloudFormation outputs as JSON")?;
    let values: BTreeMap<_, _> = outputs
        .into_iter()
        .map(|item| (item.key, item.value))
        .collect();

    let defaults = StackProfileDefaults {
        api_base: values.get("ApiUrl").cloned(),
        cognito_client_id: values.get("UserPoolClientId").cloned(),
        cognito_domain: values.get("CognitoHostedUIUrl").cloned(),
    };

    if defaults.api_base.is_none() {
        bail!("stack `{stack_name}` is missing required output ApiUrl");
    }
    if defaults.cognito_client_id.is_none() {
        bail!("stack `{stack_name}` is missing required output UserPoolClientId");
    }
    if defaults.cognito_domain.is_none() {
        bail!("stack `{stack_name}` is missing required output CognitoHostedUIUrl");
    }

    Ok(defaults)
}

fn blank_to_none(value: String) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

fn parse_sections_arg(value: Option<&str>) -> Result<Option<Vec<String>>> {
    let Some(value) = value else {
        return Ok(None);
    };
    let allowed = ["radio", "infographic", "social"];
    let sections: Vec<String> = value
        .split(',')
        .map(str::trim)
        .filter(|section| !section.is_empty())
        .map(ToString::to_string)
        .collect();

    if sections.is_empty() {
        bail!("sections must include one of: radio, infographic, social");
    }
    for section in &sections {
        if !allowed.contains(&section.as_str()) {
            bail!("invalid section `{section}`; expected radio, infographic, or social");
        }
    }
    Ok(Some(sections))
}

#[derive(Debug, Deserialize)]
struct JwtPayload {
    exp: Option<i64>,
}

fn token_expired(token: &str) -> bool {
    let payload_b64 = match token.split('.').nth(1) {
        Some(value) => value,
        None => return true,
    };
    let decoded = match base64::engine::general_purpose::URL_SAFE_NO_PAD.decode(payload_b64) {
        Ok(bytes) => bytes,
        Err(_) => return true,
    };
    let payload: JwtPayload = match serde_json::from_slice(&decoded) {
        Ok(value) => value,
        Err(_) => return true,
    };
    match payload.exp {
        Some(exp) => exp <= Utc::now().timestamp(),
        None => true,
    }
}

fn validate_history_days(days: u32) -> Result<()> {
    if days == 0 || days > 7 {
        bail!("days must be between 1 and 7 because /api/history only exposes the last 7 days");
    }
    Ok(())
}

fn filter_tracks_by_days(history: &HistoryResponse, days: u32) -> Vec<HistoryTrack> {
    let cutoff = Utc::now().timestamp() - i64::from(days) * 86_400;
    history
        .blocks
        .iter()
        .flat_map(|block| block.tracks.iter())
        .filter(|track| track.timestamp >= cutoff)
        .cloned()
        .collect()
}

fn aggregate_top_tracks(
    tracks: &[HistoryTrack],
    limit: usize,
    raw: bool,
    chart_filter: Option<&ChartFilter>,
) -> Vec<TopAggregateRow> {
    let mut counts: HashMap<String, usize> = HashMap::new();
    let mut variants: HashMap<String, HashSet<String>> = HashMap::new();

    for track in tracks {
        if chart_filter.is_some_and(|filter| filter.matches(&track.track)) {
            continue;
        }

        let key = if raw {
            track.raw_track.clone()
        } else {
            track.track.clone()
        };
        *counts.entry(key.clone()).or_default() += 1;
        variants
            .entry(key)
            .or_default()
            .insert(track.raw_track.clone());
    }

    let mut rows: Vec<_> = counts
        .into_iter()
        .map(|(track, plays)| TopAggregateRow {
            rank: 0,
            unique_raw_variants: variants.get(&track).map(|v| v.len()).unwrap_or(0),
            track,
            plays,
        })
        .collect();

    rows.sort_by(|a, b| b.plays.cmp(&a.plays).then_with(|| a.track.cmp(&b.track)));
    rows.truncate(limit);

    for (index, row) in rows.iter_mut().enumerate() {
        row.rank = index + 1;
    }

    rows
}

struct ChartFilter {
    regex_patterns: Vec<regex::Regex>,
    substring_patterns: Vec<String>,
}

impl ChartFilter {
    fn matches(&self, track_name: &str) -> bool {
        self.regex_patterns
            .iter()
            .any(|pattern| pattern.is_match(track_name))
            || self
                .substring_patterns
                .iter()
                .any(|pattern| track_name.to_lowercase().contains(pattern))
    }
}

fn build_chart_filter(patterns: Vec<String>) -> ChartFilter {
    let mut regex_patterns = Vec::new();
    let mut substring_patterns = Vec::new();

    for pattern in patterns {
        match regex::RegexBuilder::new(&pattern)
            .case_insensitive(true)
            .build()
        {
            Ok(regex) => regex_patterns.push(regex),
            Err(_) => substring_patterns.push(pattern.to_lowercase()),
        }
    }

    ChartFilter {
        regex_patterns,
        substring_patterns,
    }
}

fn summarize_tracks(days: u32, tracks: &[HistoryTrack]) -> StatsSummary {
    let unique_tracks: HashSet<_> = tracks.iter().map(|track| track.track.as_str()).collect();
    let backup_tracks = tracks.iter().filter(|track| track.backup_status).count();

    let mut status_counts: BTreeMap<String, usize> = BTreeMap::new();
    for track in tracks {
        *status_counts
            .entry(track.validation_status.clone())
            .or_default() += 1;
    }

    StatsSummary {
        days,
        total_tracks: tracks.len(),
        unique_tracks: unique_tracks.len(),
        backup_tracks,
        validation_status_counts: status_counts
            .into_iter()
            .map(|(status, count)| StatusCount { status, count })
            .collect(),
    }
}

fn render_health(output: OutputFormat, health: HealthResponse) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&health),
        OutputFormat::Table => {
            let mut table = base_table();
            table.set_header(vec!["Field", "Value"]);
            table.add_row(vec!["status", &health.status]);
            table.add_row(vec!["service", &health.service]);
            println!("{table}");
            Ok(())
        }
    }
}

fn render_profile(
    output: OutputFormat,
    config_path: &std::path::Path,
    profile_name: &str,
    profile: &ProfileConfig,
    stored: &StoredConfig,
) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&serde_json::json!({
            "config_path": config_path.display().to_string(),
            "selected_profile": profile_name,
            "active_profile": stored.active_profile.clone(),
            "profiles": stored.profiles.keys().cloned().collect::<Vec<_>>(),
            "stack_name": profile.stack_name.clone(),
            "region": profile.region.clone(),
            "api_base": profile.api_base.clone(),
            "token_configured": profile.token.as_ref().map(|token| !token.is_empty()).unwrap_or(false),
            "token_expired": profile.token.as_ref().map(|token| token_expired(token)).unwrap_or(true),
            "cognito_client_id": profile.cognito_client_id.clone(),
            "cognito_domain": profile.cognito_domain.clone(),
            "cognito_redirect_uri": profile.cognito_redirect_uri.clone(),
        })),
        OutputFormat::Table => {
            let mut table = base_table();
            table.set_header(vec!["Field", "Value"]);
            table.add_row(vec![
                Cell::new("config_path"),
                Cell::new(config_path.display().to_string()),
            ]);
            table.add_row(vec![Cell::new("selected_profile"), Cell::new(profile_name)]);
            table.add_row(vec![
                Cell::new("active_profile"),
                Cell::new(
                    stored
                        .active_profile
                        .clone()
                        .unwrap_or_else(|| "(not set)".to_string()),
                ),
            ]);
            table.add_row(vec![
                Cell::new("available_profiles"),
                Cell::new(
                    stored
                        .profiles
                        .keys()
                        .cloned()
                        .collect::<Vec<_>>()
                        .join(", "),
                ),
            ]);
            table.add_row(vec![
                Cell::new("stack_name"),
                Cell::new(
                    profile
                        .stack_name
                        .clone()
                        .unwrap_or_else(|| "(not set)".to_string()),
                ),
            ]);
            table.add_row(vec![
                Cell::new("region"),
                Cell::new(
                    profile
                        .region
                        .clone()
                        .unwrap_or_else(|| "(aws cli default)".to_string()),
                ),
            ]);
            table.add_row(vec![
                Cell::new("api_base"),
                Cell::new(
                    profile
                        .api_base
                        .clone()
                        .unwrap_or_else(|| "(not set)".to_string()),
                ),
            ]);
            table.add_row(vec![
                Cell::new("token_configured"),
                Cell::new(if profile.token.as_ref().is_some_and(|t| !t.is_empty()) {
                    "true"
                } else {
                    "false"
                }),
            ]);
            table.add_row(vec![
                Cell::new("token_expired"),
                Cell::new(
                    if profile
                        .token
                        .as_ref()
                        .is_some_and(|token| token_expired(token))
                    {
                        "true"
                    } else {
                        "false"
                    },
                ),
            ]);
            table.add_row(vec![
                Cell::new("cognito_client_id"),
                Cell::new(
                    profile
                        .cognito_client_id
                        .clone()
                        .unwrap_or_else(|| "(not set)".to_string()),
                ),
            ]);
            table.add_row(vec![
                Cell::new("cognito_domain"),
                Cell::new(
                    profile
                        .cognito_domain
                        .clone()
                        .unwrap_or_else(|| "(not set)".to_string()),
                ),
            ]);
            table.add_row(vec![
                Cell::new("cognito_redirect_uri"),
                Cell::new(
                    profile
                        .cognito_redirect_uri
                        .clone()
                        .unwrap_or_else(|| "http://localhost:8000/admin.html".to_string()),
                ),
            ]);
            println!("{table}");
            Ok(())
        }
    }
}

fn render_top10(output: OutputFormat, top10: Top10Response) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&top10),
        OutputFormat::Table => {
            println!("Week: {} -> {}", top10.week_start, top10.week_end);
            let mut table = base_table();
            table.set_header(vec!["Rank", "Track", "Plays", "Prev", "Move", "Delta"]);
            for entry in top10.top10 {
                table.add_row(vec![
                    Cell::new(entry.rank),
                    Cell::new(entry.track),
                    Cell::new(entry.play_count),
                    Cell::new(
                        entry
                            .previous_rank
                            .map_or("-".to_string(), |v| v.to_string()),
                    ),
                    Cell::new(entry.movement),
                    Cell::new(
                        entry
                            .movement_delta
                            .map_or("-".to_string(), |v| v.to_string()),
                    ),
                ]);
            }
            println!("{table}");
            Ok(())
        }
    }
}

fn render_top10_history(output: OutputFormat, response: Top10HistoryResponse) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&response),
        OutputFormat::Table => {
            let mut table = base_table();
            if response.detail {
                table.set_header(vec!["Week", "Start", "End", "Tracks", "Plays", "Unique"]);
            } else {
                table.set_header(vec!["Week", "Start", "End", "Tracks", "Plays", "Href"]);
            }

            for week in response.weeks {
                if response.detail {
                    table.add_row(vec![
                        Cell::new(value_string(&week, "week_id")),
                        Cell::new(value_string(&week, "week_start")),
                        Cell::new(value_string(&week, "week_end")),
                        Cell::new(
                            week.get("top10")
                                .and_then(|value| value.as_array())
                                .map(|items| items.len().to_string())
                                .unwrap_or_else(|| "-".to_string()),
                        ),
                        Cell::new(value_at(&week, "/summary/total_plays")),
                        Cell::new(value_at(&week, "/summary/unique_tracks")),
                    ]);
                } else {
                    table.add_row(vec![
                        Cell::new(value_string(&week, "week_id")),
                        Cell::new(value_string(&week, "week_start")),
                        Cell::new(value_string(&week, "week_end")),
                        Cell::new(value_at(&week, "/top10_count")),
                        Cell::new(value_at(&week, "/total_plays")),
                        Cell::new(value_string(&week, "href")),
                    ]);
                }
            }
            println!("{table}");
            if let Some(next_token) = response.next_token {
                println!("next_token: {next_token}");
            }
            Ok(())
        }
    }
}

fn render_top10_history_week(
    output: OutputFormat,
    response: Top10HistoryWeekResponse,
) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&response),
        OutputFormat::Table => {
            let snapshot = response.snapshot;
            println!(
                "Week: {} -> {}",
                value_string(&snapshot, "week_start"),
                value_string(&snapshot, "week_end")
            );
            println!(
                "Snapshot: {} ({})",
                value_string(&snapshot, "snapshot_key"),
                value_string(&snapshot, "snapshot_type")
            );

            let mut table = base_table();
            table.set_header(vec!["Rank", "Track", "Plays", "Prev", "Move", "Delta"]);
            if let Some(entries) = snapshot.get("top10").and_then(|value| value.as_array()) {
                for entry in entries {
                    table.add_row(vec![
                        Cell::new(value_at(entry, "/rank")),
                        Cell::new(value_string(entry, "track")),
                        Cell::new(value_at(entry, "/play_count")),
                        Cell::new(value_at(entry, "/previous_rank")),
                        Cell::new(value_string(entry, "movement")),
                        Cell::new(value_at(entry, "/movement_delta")),
                    ]);
                }
            }
            println!("{table}");
            Ok(())
        }
    }
}

fn render_config(output: OutputFormat, config: ConfigResponse) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&config),
        OutputFormat::Table => {
            let mut schedule_table = base_table();
            schedule_table.set_header(vec!["Config", "Day", "Hour"]);
            add_schedule_row(
                &mut schedule_table,
                "chart_generation",
                &config.chart_generation,
            );
            add_schedule_row(
                &mut schedule_table,
                "playlist_generation",
                &config.playlist_generation,
            );
            println!("{schedule_table}");

            let mut filters_table = base_table();
            filters_table.set_header(vec!["Top 10 Filters"]);
            if config.top10_filters.is_empty() {
                filters_table.add_row(vec![Cell::new("(none)")]);
            } else {
                for filter in config.top10_filters {
                    filters_table.add_row(vec![Cell::new(filter)]);
                }
            }
            println!("{filters_table}");
            Ok(())
        }
    }
}

fn render_spotify_status(
    output: OutputFormat,
    status: models::SpotifyStatusResponse,
) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&status),
        OutputFormat::Table => {
            let mut table = base_table();
            table.set_header(vec!["Field", "Value"]);
            table.add_row(vec![
                "connected",
                if status.connected { "true" } else { "false" },
            ]);
            table.add_row(vec!["message", &status.message]);
            println!("{table}");
            Ok(())
        }
    }
}

fn render_campaigns(output: OutputFormat, campaigns: CampaignsResponse) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&campaigns),
        OutputFormat::Table => {
            let mut table = base_table();
            table.set_header(vec![
                "Week",
                "Status",
                "Generated",
                "Generated By",
                "Requested By",
                "Snapshot",
            ]);
            for campaign in campaigns.campaigns {
                table.add_row(vec![
                    Cell::new(campaign.week_id.unwrap_or_else(|| "-".to_string())),
                    Cell::new(campaign.status.unwrap_or_else(|| "-".to_string())),
                    Cell::new(campaign.generated_at.unwrap_or_else(|| "-".to_string())),
                    Cell::new(campaign.generated_by.unwrap_or_else(|| "-".to_string())),
                    Cell::new(campaign.requested_by.unwrap_or_else(|| "-".to_string())),
                    Cell::new(campaign.snapshot_key.unwrap_or_else(|| "-".to_string())),
                ]);
            }
            println!("{table}");
            Ok(())
        }
    }
}

fn render_campaign(output: OutputFormat, response: CampaignResponse) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&response),
        OutputFormat::Table => {
            let campaign = response.campaign;
            let mut table = base_table();
            table.set_header(vec!["Field", "Value"]);
            for key in [
                "week_id",
                "status",
                "generated_at",
                "generated_by",
                "requested_by",
                "source_snapshot_key",
            ] {
                table.add_row(vec![
                    Cell::new(key),
                    Cell::new(
                        campaign
                            .get(key)
                            .and_then(|value| value.as_str())
                            .unwrap_or("-"),
                    ),
                ]);
            }

            let radio_count = campaign
                .pointer("/radio_reads/position_reads")
                .and_then(|value| value.as_array())
                .map(|items| items.len())
                .unwrap_or(0);
            let track_card_count = campaign
                .pointer("/infographic/track_cards")
                .and_then(|value| value.as_array())
                .map(|items| items.len())
                .unwrap_or(0);
            table.add_row(vec![Cell::new("radio_reads"), Cell::new(radio_count)]);
            table.add_row(vec![
                Cell::new("infographic_cards"),
                Cell::new(track_card_count),
            ]);
            table.add_row(vec![
                Cell::new("social_sections"),
                Cell::new(
                    campaign
                        .get("social")
                        .and_then(|value| value.as_object())
                        .map(|items| items.len())
                        .unwrap_or(0),
                ),
            ]);
            println!("{table}");
            Ok(())
        }
    }
}

fn render_campaign_generate(
    output: OutputFormat,
    response: CampaignGenerateResponse,
) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&response),
        OutputFormat::Table => {
            println!("{}", response.message);
            render_campaign(
                OutputFormat::Table,
                CampaignResponse {
                    campaign: response.campaign,
                },
            )
        }
    }
}

fn render_history(
    output: OutputFormat,
    days: u32,
    flat: bool,
    limit: Option<usize>,
    history: &HistoryResponse,
    filtered_tracks: &[HistoryTrack],
) -> Result<()> {
    if matches!(output, OutputFormat::Json) {
        if flat {
            let mut tracks = filtered_tracks.to_vec();
            tracks.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
            if let Some(limit) = limit {
                tracks.truncate(limit);
            }
            return print_json(&tracks);
        }

        let cutoff = Utc::now().timestamp() - i64::from(days) * 86_400;
        let filtered_blocks: Vec<_> = history
            .blocks
            .iter()
            .filter_map(|block| {
                let tracks: Vec<_> = block
                    .tracks
                    .iter()
                    .filter(|track| track.timestamp >= cutoff)
                    .cloned()
                    .collect();
                if tracks.is_empty() {
                    None
                } else {
                    Some(serde_json::json!({
                        "block_timestamp": block.block_timestamp,
                        "block_label": block.block_label,
                        "tracks": tracks,
                    }))
                }
            })
            .collect();

        return print_json(&serde_json::json!({
            "days": days,
            "blocks": filtered_blocks,
            "total_tracks": filtered_tracks.len(),
        }));
    }

    if flat {
        let mut tracks = filtered_tracks.to_vec();
        tracks.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
        if let Some(limit) = limit {
            tracks.truncate(limit);
        }

        let mut table = base_table();
        table.set_header(vec!["Time", "Track", "Raw", "Status", "Backup"]);
        for track in tracks {
            table.add_row(vec![
                Cell::new(track.formatted_time),
                Cell::new(track.track),
                Cell::new(track.raw_track),
                Cell::new(track.validation_status),
                Cell::new(if track.backup_status { "yes" } else { "no" }),
            ]);
        }
        println!("{table}");
        return Ok(());
    }

    println!("Showing history for the last {days} day(s)");
    for block in &history.blocks {
        let mut rows: Vec<_> = block
            .tracks
            .iter()
            .filter(|track| track.timestamp >= Utc::now().timestamp() - i64::from(days) * 86_400)
            .collect();

        if rows.is_empty() {
            continue;
        }

        rows.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
        println!();
        println!("{}", block.block_label);
        let mut table = base_table();
        table.set_header(vec!["Time", "Track", "Status", "Backup"]);
        for track in rows {
            table.add_row(vec![
                Cell::new(&track.formatted_time),
                Cell::new(&track.track),
                Cell::new(&track.validation_status),
                Cell::new(if track.backup_status { "yes" } else { "no" }),
            ]);
        }
        println!("{table}");
    }

    Ok(())
}

fn render_top_aggregate(
    output: OutputFormat,
    days: u32,
    raw: bool,
    chart_rules_applied: bool,
    rows: Vec<TopAggregateRow>,
) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&serde_json::json!({
            "days": days,
            "source": if raw { "raw_track" } else { "track" },
            "chart_rules_applied": chart_rules_applied,
            "rows": rows,
        })),
        OutputFormat::Table => {
            println!(
                "Top tracks over the last {days} day(s) using {}{}",
                if raw { "raw titles" } else { "display titles" },
                if chart_rules_applied {
                    " with chart filters applied"
                } else {
                    ""
                }
            );
            let mut table = base_table();
            table.set_header(vec!["Rank", "Track", "Plays", "Raw Variants"]);
            for row in rows {
                table.add_row(vec![
                    Cell::new(row.rank),
                    Cell::new(row.track),
                    Cell::new(row.plays),
                    Cell::new(row.unique_raw_variants),
                ]);
            }
            println!("{table}");
            Ok(())
        }
    }
}

fn render_stats(output: OutputFormat, summary: StatsSummary) -> Result<()> {
    match output {
        OutputFormat::Json => print_json(&summary),
        OutputFormat::Table => {
            let mut summary_table = base_table();
            summary_table.set_header(vec!["Metric", "Value"]);
            summary_table.add_row(vec!["days", &summary.days.to_string()]);
            summary_table.add_row(vec!["total_tracks", &summary.total_tracks.to_string()]);
            summary_table.add_row(vec!["unique_tracks", &summary.unique_tracks.to_string()]);
            summary_table.add_row(vec!["backup_tracks", &summary.backup_tracks.to_string()]);
            println!("{summary_table}");

            let mut status_table = base_table();
            status_table.set_header(vec!["Validation Status", "Count"]);
            for status in summary.validation_status_counts {
                status_table.add_row(vec![Cell::new(status.status), Cell::new(status.count)]);
            }
            println!("{status_table}");
            Ok(())
        }
    }
}

fn add_schedule_row(table: &mut Table, name: &str, schedule: &ScheduleConfig) {
    table.add_row(vec![
        Cell::new(name),
        Cell::new(&schedule.day),
        Cell::new(schedule.hour),
    ]);
}

fn print_json<T: serde::Serialize>(value: &T) -> Result<()> {
    println!("{}", serde_json::to_string_pretty(value)?);
    Ok(())
}

fn value_string(value: &serde_json::Value, key: &str) -> String {
    value
        .get(key)
        .and_then(|item| item.as_str())
        .unwrap_or("-")
        .to_string()
}

fn value_at(value: &serde_json::Value, pointer: &str) -> String {
    let Some(item) = value.pointer(pointer) else {
        return "-".to_string();
    };
    match item {
        serde_json::Value::Null => "-".to_string(),
        serde_json::Value::String(value) => value.clone(),
        serde_json::Value::Number(value) => value.to_string(),
        serde_json::Value::Bool(value) => value.to_string(),
        _ => serde_json::to_string(item).unwrap_or_else(|_| "-".to_string()),
    }
}

fn base_table() -> Table {
    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_content_arrangement(ContentArrangement::Dynamic);
    table
}

#[cfg(test)]
mod tests {
    use super::{aggregate_top_tracks, build_chart_filter, summarize_tracks};
    use crate::models::HistoryTrack;

    fn track(track: &str, raw_track: &str, status: &str, backup: bool) -> HistoryTrack {
        HistoryTrack {
            timestamp: 1_700_000_000,
            formatted_time: "2024-01-01T00:00:00-08:00".to_string(),
            track: track.to_string(),
            raw_track: raw_track.to_string(),
            validation_status: status.to_string(),
            artist: None,
            title: None,
            backup_status: backup,
        }
    }

    #[test]
    fn aggregates_canonical_tracks() {
        let tracks = vec![
            track("A - Song", "A - Song", "validated", false),
            track("A - Song", "A - Song (Clean)", "validated", false),
            track("B - Song", "B - Song", "unvalidated", true),
        ];

        let rows = aggregate_top_tracks(&tracks, 10, false, None);
        assert_eq!(rows[0].track, "A - Song");
        assert_eq!(rows[0].plays, 2);
        assert_eq!(rows[0].unique_raw_variants, 2);
    }

    #[test]
    fn summarizes_validation_counts() {
        let tracks = vec![
            track("A - Song", "A - Song", "validated", false),
            track("B - Song", "B - Song", "unvalidated", true),
            track("C - Song", "C - Song", "promotional", false),
        ];

        let summary = summarize_tracks(3, &tracks);
        assert_eq!(summary.total_tracks, 3);
        assert_eq!(summary.unique_tracks, 3);
        assert_eq!(summary.backup_tracks, 1);
        assert_eq!(summary.validation_status_counts.len(), 3);
    }

    #[test]
    fn applies_chart_filters_to_top_aggregation() {
        let tracks = vec![
            track(
                "Muddy's Music Cafe - Promo",
                "Muddy's Music Cafe - Promo",
                "promotional",
                false,
            ),
            track("A - Song", "A - Song", "validated", false),
            track("A - Song", "A - Song", "validated", false),
        ];

        let filter = build_chart_filter(vec![r"^Muddy'?s".to_string()]);
        let rows = aggregate_top_tracks(&tracks, 10, false, Some(&filter));

        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].track, "A - Song");
        assert_eq!(rows[0].plays, 2);
    }
}
