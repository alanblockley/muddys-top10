use anyhow::{Context, Result, anyhow, bail};
use reqwest::blocking::{Client, Response};
use serde::Serialize;
use serde::de::DeserializeOwned;

use crate::models::{
    CampaignGenerateResponse, CampaignResponse, CampaignsResponse, ConfigResponse, HealthResponse,
    HistoryResponse, SpotifyStatusResponse, Top10HistoryResponse, Top10HistoryWeekResponse,
    Top10Response,
};

pub struct ApiClient {
    client: Client,
    api_root: String,
    token: Option<String>,
}

impl ApiClient {
    pub fn new(base_url: &str, token: Option<String>) -> Result<Self> {
        let client = Client::builder()
            .user_agent(concat!(
                env!("CARGO_PKG_NAME"),
                "/",
                env!("CARGO_PKG_VERSION")
            ))
            .build()
            .context("failed to build HTTP client")?;

        Ok(Self {
            client,
            api_root: normalize_api_root(base_url)?,
            token,
        })
    }

    pub fn health(&self) -> Result<HealthResponse> {
        self.get("/health", true)
    }

    pub fn top10(&self) -> Result<Top10Response> {
        self.get("/top10", true)
    }

    pub fn config(&self) -> Result<ConfigResponse> {
        self.get("/config", true)
    }

    pub fn history(&self) -> Result<HistoryResponse> {
        self.get("/history", true)
    }

    pub fn spotify_status(&self) -> Result<SpotifyStatusResponse> {
        self.get("/spotify/status", true)
    }

    pub fn campaigns(&self, limit: usize) -> Result<CampaignsResponse> {
        self.get(&format!("/campaigns?limit={limit}"), true)
    }

    pub fn campaign(&self, week_id: &str) -> Result<CampaignResponse> {
        self.get(&format!("/campaigns/{week_id}"), true)
    }

    pub fn generate_campaign(
        &self,
        week_id: Option<&str>,
        sections: Option<&[String]>,
    ) -> Result<CampaignGenerateResponse> {
        #[derive(Serialize)]
        struct Body<'a> {
            #[serde(skip_serializing_if = "Option::is_none")]
            week_id: Option<&'a str>,
            #[serde(skip_serializing_if = "Option::is_none")]
            sections: Option<&'a [String]>,
        }

        self.post("/campaigns/generate", &Body { week_id, sections }, true)
    }

    pub fn top10_history(
        &self,
        limit: usize,
        from: Option<&str>,
        to: Option<&str>,
        detail: bool,
        all: bool,
    ) -> Result<Top10HistoryResponse> {
        let mut params = vec![format!("limit={limit}")];
        if let Some(from) = from {
            params.push(format!("from={}", url_encode(from)));
        }
        if let Some(to) = to {
            params.push(format!("to={}", url_encode(to)));
        }
        if detail {
            params.push("detail=true".to_string());
        }
        if all {
            params.push("all=true".to_string());
        }
        self.get(&format!("/top10/history?{}", params.join("&")), true)
    }

    pub fn top10_history_week(&self, week_id: &str) -> Result<Top10HistoryWeekResponse> {
        self.get(&format!("/top10/history/{}", url_encode(week_id)), true)
    }

    fn get<T>(&self, path: &str, requires_auth: bool) -> Result<T>
    where
        T: DeserializeOwned,
    {
        let url = format!("{}{}", self.api_root, path);
        let mut request = self.client.get(url);

        if let Some(token) = &self.token {
            request = request.bearer_auth(token);
        } else if requires_auth {
            bail!("this command requires a bearer token; pass --token or set MUDDYS_API_TOKEN");
        }

        let response = request.send().context("request failed")?;
        decode_response(response)
    }

    fn post<T, B>(&self, path: &str, body: &B, requires_auth: bool) -> Result<T>
    where
        T: DeserializeOwned,
        B: Serialize + ?Sized,
    {
        let url = format!("{}{}", self.api_root, path);
        let mut request = self.client.post(url).json(body);

        if let Some(token) = &self.token {
            request = request.bearer_auth(token);
        } else if requires_auth {
            bail!("this command requires a bearer token; pass --token or set MUDDYS_API_TOKEN");
        }

        let response = request.send().context("request failed")?;
        decode_response(response)
    }
}

fn url_encode(value: &str) -> String {
    url::form_urlencoded::byte_serialize(value.as_bytes()).collect()
}

fn decode_response<T>(response: Response) -> Result<T>
where
    T: DeserializeOwned,
{
    let status = response.status();
    if !status.is_success() {
        let body = response.text().unwrap_or_default();
        return Err(anyhow!("API request failed with {}: {}", status, body));
    }

    response
        .json()
        .context("failed to decode API response as JSON")
}

pub fn normalize_api_root(base_url: &str) -> Result<String> {
    let trimmed = base_url.trim().trim_end_matches('/');
    if trimmed.is_empty() {
        bail!("API base URL cannot be empty");
    }

    if !(trimmed.starts_with("http://") || trimmed.starts_with("https://")) {
        bail!("API base URL must start with http:// or https://");
    }

    if trimmed.ends_with("/api") {
        Ok(trimmed.to_string())
    } else {
        Ok(format!("{trimmed}/api"))
    }
}

#[cfg(test)]
mod tests {
    use super::normalize_api_root;

    #[test]
    fn normalizes_plain_origin() {
        assert_eq!(
            normalize_api_root("https://example.com").unwrap(),
            "https://example.com/api"
        );
    }

    #[test]
    fn preserves_api_suffix() {
        assert_eq!(
            normalize_api_root("https://example.com/api/").unwrap(),
            "https://example.com/api"
        );
    }
}
