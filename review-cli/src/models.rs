use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Deserialize, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub service: String,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Top10Response {
    pub top10: Vec<Top10Entry>,
    pub chart_date: String,
    pub week_start: String,
    pub week_end: String,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Top10Entry {
    pub rank: u32,
    pub track: String,
    pub play_count: u32,
    pub previous_rank: Option<u32>,
    pub movement: String,
    pub movement_delta: Option<i32>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct ConfigResponse {
    pub chart_generation: ScheduleConfig,
    pub top10_filters: Vec<String>,
    pub playlist_generation: ScheduleConfig,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ScheduleConfig {
    pub day: String,
    pub hour: u32,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct HistoryResponse {
    pub blocks: Vec<HistoryBlock>,
    pub total_tracks: usize,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct HistoryBlock {
    pub block_timestamp: i64,
    pub block_label: String,
    pub tracks: Vec<HistoryTrack>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct HistoryTrack {
    pub timestamp: i64,
    pub formatted_time: String,
    pub track: String,
    pub raw_track: String,
    pub validation_status: String,
    pub artist: Option<String>,
    pub title: Option<String>,
    #[serde(default)]
    pub backup_status: bool,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct SpotifyStatusResponse {
    pub connected: bool,
    pub message: String,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CampaignsResponse {
    pub campaigns: Vec<CampaignIndexEntry>,
    pub count: usize,
    pub limit: usize,
    pub next_token: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CampaignIndexEntry {
    pub week_id: Option<String>,
    pub snapshot_key: Option<String>,
    pub status: Option<String>,
    pub generated_at: Option<String>,
    pub generated_by: Option<String>,
    pub requested_by: Option<String>,
    pub reviewed_at: Option<String>,
    pub approved_at: Option<String>,
    pub published_at: Option<String>,
    pub href: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CampaignResponse {
    pub campaign: Value,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CampaignGenerateResponse {
    pub message: String,
    pub campaign: Value,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Top10HistoryResponse {
    pub weeks: Vec<Value>,
    pub count: usize,
    pub detail: bool,
    pub from: Option<String>,
    pub to: Option<String>,
    pub limit: Option<usize>,
    pub next_token: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Top10HistoryWeekResponse {
    pub snapshot: Value,
}

#[derive(Debug, Serialize)]
pub struct TopAggregateRow {
    pub rank: usize,
    pub track: String,
    pub plays: usize,
    pub unique_raw_variants: usize,
}

#[derive(Debug, Serialize)]
pub struct StatsSummary {
    pub days: u32,
    pub total_tracks: usize,
    pub unique_tracks: usize,
    pub backup_tracks: usize,
    pub validation_status_counts: Vec<StatusCount>,
}

#[derive(Debug, Serialize)]
pub struct StatusCount {
    pub status: String,
    pub count: usize,
}
