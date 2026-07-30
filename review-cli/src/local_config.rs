use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct ProfileConfig {
    pub stack_name: Option<String>,
    pub region: Option<String>,
    pub api_base: Option<String>,
    pub token: Option<String>,
    pub cognito_client_id: Option<String>,
    pub cognito_domain: Option<String>,
    pub cognito_redirect_uri: Option<String>,
}

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct StoredConfig {
    pub stack_name: Option<String>,
    pub region: Option<String>,
    pub api_base: Option<String>,
    pub token: Option<String>,
    pub cognito_client_id: Option<String>,
    pub cognito_domain: Option<String>,
    pub cognito_redirect_uri: Option<String>,
    #[serde(default)]
    pub active_profile: Option<String>,
    #[serde(default)]
    pub profiles: BTreeMap<String, ProfileConfig>,
}

impl StoredConfig {
    pub fn profile_name(&self, requested: Option<&str>) -> String {
        requested
            .or(self.active_profile.as_deref())
            .unwrap_or("default")
            .to_string()
    }

    pub fn profile(&self, name: &str) -> ProfileConfig {
        self.profiles.get(name).cloned().unwrap_or_else(|| {
            if name == "default" {
                self.legacy_profile()
            } else {
                ProfileConfig::default()
            }
        })
    }

    pub fn set_profile(&mut self, name: &str, profile: ProfileConfig) {
        self.profiles.insert(name.to_string(), profile.clone());
        self.active_profile = Some(name.to_string());
        if name == "default" {
            self.stack_name = profile.stack_name;
            self.region = profile.region;
            self.api_base = profile.api_base;
            self.token = profile.token;
            self.cognito_client_id = profile.cognito_client_id;
            self.cognito_domain = profile.cognito_domain;
            self.cognito_redirect_uri = profile.cognito_redirect_uri;
        }
    }

    fn legacy_profile(&self) -> ProfileConfig {
        ProfileConfig {
            stack_name: self.stack_name.clone(),
            region: self.region.clone(),
            api_base: self.api_base.clone(),
            token: self.token.clone(),
            cognito_client_id: self.cognito_client_id.clone(),
            cognito_domain: self.cognito_domain.clone(),
            cognito_redirect_uri: self.cognito_redirect_uri.clone(),
        }
    }
}

pub fn resolve_config_path(cli_path: Option<&str>) -> Result<PathBuf> {
    if let Some(path) = cli_path {
        return Ok(PathBuf::from(path));
    }

    if let Ok(path) = env::var("MUDDYS_CONFIG_PATH") {
        if !path.trim().is_empty() {
            return Ok(PathBuf::from(path));
        }
    }

    if let Ok(xdg_home) = env::var("XDG_CONFIG_HOME") {
        if !xdg_home.trim().is_empty() {
            return Ok(PathBuf::from(xdg_home)
                .join("review-cli")
                .join("config.json"));
        }
    }

    if let Ok(home) = env::var("HOME") {
        if !home.trim().is_empty() {
            return Ok(PathBuf::from(home)
                .join(".config")
                .join("review-cli")
                .join("config.json"));
        }
    }

    bail!("unable to determine config path; set --config or MUDDYS_CONFIG_PATH");
}

pub fn load_config(path: &Path) -> Result<StoredConfig> {
    if !path.exists() {
        return Ok(StoredConfig::default());
    }

    let raw = fs::read_to_string(path)
        .with_context(|| format!("failed to read config file at {}", path.display()))?;
    if raw.trim().is_empty() {
        return Ok(StoredConfig::default());
    }
    let config = serde_json::from_str(&raw)
        .with_context(|| format!("failed to parse config file at {}", path.display()))?;
    Ok(config)
}

pub fn save_config(path: &Path, config: &StoredConfig) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create config directory {}", parent.display()))?;
    }

    let json = serde_json::to_string_pretty(config)?;
    fs::write(path, json)
        .with_context(|| format!("failed to write config file at {}", path.display()))
}

pub fn prompt(label: &str, current: Option<&str>) -> Result<String> {
    let mut stdout = io::stdout();
    if let Some(current) = current {
        write!(stdout, "{} [{}]: ", label, current)?;
    } else {
        write!(stdout, "{}: ", label)?;
    }
    stdout.flush()?;

    let mut input = String::new();
    io::stdin().read_line(&mut input)?;
    let trimmed = input.trim();
    if trimmed.is_empty() {
        Ok(current.unwrap_or_default().to_string())
    } else {
        Ok(trimmed.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::{ProfileConfig, StoredConfig, load_config, save_config};
    use std::fs;

    #[test]
    fn round_trips_config_file() {
        let path =
            std::env::temp_dir().join(format!("review-cli-test-{}.json", std::process::id()));
        let config = StoredConfig {
            api_base: Some("https://example.com".to_string()),
            token: Some("abc".to_string()),
            cognito_client_id: Some("client".to_string()),
            cognito_domain: Some("https://example.auth.us-west-2.amazoncognito.com".to_string()),
            cognito_redirect_uri: Some("http://localhost:8000/admin.html".to_string()),
            ..StoredConfig::default()
        };

        save_config(&path, &config).unwrap();
        let loaded = load_config(&path).unwrap();
        fs::remove_file(&path).unwrap();

        assert_eq!(loaded.api_base.as_deref(), Some("https://example.com"));
        assert_eq!(loaded.token.as_deref(), Some("abc"));
        assert_eq!(loaded.cognito_client_id.as_deref(), Some("client"));
    }

    #[test]
    fn round_trips_named_profiles() {
        let path = std::env::temp_dir().join(format!(
            "review-cli-profile-test-{}.json",
            std::process::id()
        ));
        let mut config = StoredConfig::default();
        config.set_profile(
            "dev",
            ProfileConfig {
                stack_name: Some("teleport-dev-muddys-top-10".to_string()),
                region: Some("us-west-2".to_string()),
                api_base: Some("https://dev.example.com".to_string()),
                token: Some("dev-token".to_string()),
                cognito_client_id: Some("dev-client".to_string()),
                cognito_domain: Some("https://dev.auth.us-west-2.amazoncognito.com".to_string()),
                cognito_redirect_uri: Some("http://localhost:0/admin.html".to_string()),
            },
        );

        save_config(&path, &config).unwrap();
        let loaded = load_config(&path).unwrap();
        fs::remove_file(&path).unwrap();

        assert_eq!(loaded.active_profile.as_deref(), Some("dev"));
        assert_eq!(
            loaded.profile("dev").api_base.as_deref(),
            Some("https://dev.example.com")
        );
    }
}
