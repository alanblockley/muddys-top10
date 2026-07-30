use std::io::{Read, Write};
use std::net::TcpListener;
use std::path::Path;
use std::thread;
use std::time::{Duration, Instant};

use anyhow::{Context, Result, bail};
use serde::Deserialize;
use url::Url;

use crate::local_config::ProfileConfig;

#[derive(Debug)]
pub struct CognitoSettings {
    pub client_id: String,
    pub domain: String,
    pub redirect_uri: String,
}

#[derive(Debug, Deserialize)]
struct TokenPayload {
    id_token: String,
}

pub fn resolve_cognito_settings(profile: &ProfileConfig) -> Result<CognitoSettings> {
    Ok(CognitoSettings {
        client_id: profile
            .cognito_client_id
            .clone()
            .context("Cognito client ID is not configured; run `review-cli setup`")?,
        domain: profile
            .cognito_domain
            .clone()
            .context("Cognito domain is not configured; run `review-cli setup`")?,
        redirect_uri: profile
            .cognito_redirect_uri
            .clone()
            .unwrap_or_else(|| "http://localhost:8000/admin.html".to_string()),
    })
}

pub fn build_login_url(settings: &CognitoSettings) -> Result<String> {
    let mut url = Url::parse(&format!(
        "{}/oauth2/authorize",
        settings.domain.trim_end_matches('/')
    ))
    .context("invalid Cognito domain URL")?;
    url.query_pairs_mut()
        .append_pair("client_id", &settings.client_id)
        .append_pair("response_type", "token")
        .append_pair("scope", "email openid profile")
        .append_pair("redirect_uri", &settings.redirect_uri);
    Ok(url.to_string())
}

pub fn perform_hosted_ui_login(config_path: &Path, profile: &mut ProfileConfig) -> Result<String> {
    let settings = resolve_cognito_settings(profile)?;
    let callback = bind_callback_listener(&settings.redirect_uri)?;
    let login_url = build_login_url(&CognitoSettings {
        client_id: settings.client_id,
        domain: settings.domain,
        redirect_uri: callback.redirect_uri.to_string(),
    })?;

    println!("Open this URL in a browser and sign in:");
    println!("{login_url}");
    println!();
    println!(
        "Waiting for Cognito callback on {}://{}:{}{}",
        callback.redirect_uri.scheme(),
        callback.host,
        callback.port,
        callback.request_path
    );

    let token = wait_for_token(callback.listener, &callback.request_path)?;
    profile.token = Some(token.clone());
    println!("Captured bearer token for {}", config_path.display());
    Ok(token)
}

struct CallbackListener {
    listener: TcpListener,
    redirect_uri: Url,
    host: String,
    port: u16,
    request_path: String,
}

fn bind_callback_listener(redirect_uri: &str) -> Result<CallbackListener> {
    let redirect = Url::parse(redirect_uri).context("invalid redirect URI")?;
    let host = redirect.host_str().unwrap_or("127.0.0.1").to_string();
    let configured_port = redirect
        .port_or_known_default()
        .context("redirect URI must include a port, or use port 0 for a random local port")?;

    let listener = TcpListener::bind((host.as_str(), configured_port)).with_context(|| {
        format!(
            "failed to bind local callback server on {}:{}",
            host, configured_port
        )
    })?;
    listener
        .set_nonblocking(true)
        .context("failed to make callback server non-blocking")?;

    let port = listener
        .local_addr()
        .context("failed to inspect local callback server address")?
        .port();
    let redirect = redirect_uri_with_port(redirect, port)?;
    let request_path = callback_request_path(&redirect);

    Ok(CallbackListener {
        listener,
        redirect_uri: redirect,
        host,
        port,
        request_path,
    })
}

fn redirect_uri_with_port(mut redirect: Url, port: u16) -> Result<Url> {
    if redirect.set_port(Some(port)).is_err() {
        bail!("failed to apply local callback port to redirect URI");
    }
    Ok(redirect)
}

fn callback_request_path(redirect: &Url) -> String {
    match redirect.query() {
        Some(query) => format!("{}?{}", redirect.path(), query),
        None => redirect.path().to_string(),
    }
}

fn wait_for_token(listener: TcpListener, callback_path: &str) -> Result<String> {
    let deadline = Instant::now() + Duration::from_secs(300);

    loop {
        if Instant::now() > deadline {
            bail!("timed out waiting for Cognito login callback");
        }

        match listener.accept() {
            Ok((mut stream, _addr)) => {
                let mut buffer = [0_u8; 16_384];
                let bytes_read = stream
                    .read(&mut buffer)
                    .context("failed reading callback request")?;
                let request = String::from_utf8_lossy(&buffer[..bytes_read]).to_string();
                let (status_line, headers, body) = split_http_request(&request)?;
                let mut parts = status_line.split_whitespace();
                let method = parts.next().unwrap_or_default();
                let path = parts.next().unwrap_or_default();

                if method == "GET" && path == callback_path {
                    let html = callback_page_html(callback_path);
                    write_http_response(&mut stream, "200 OK", "text/html", html.as_bytes())?;
                } else if method == "POST" && path == "/token-callback" {
                    let content_length = parse_content_length(headers).unwrap_or(body.len());
                    let payload = if body.len() >= content_length {
                        body[..content_length].to_string()
                    } else {
                        body.to_string()
                    };
                    let token_payload: TokenPayload = serde_json::from_str(payload.trim())
                        .context("failed to parse token callback payload")?;
                    write_http_response(
                        &mut stream,
                        "200 OK",
                        "text/html",
                        success_page_html().as_bytes(),
                    )?;
                    return Ok(token_payload.id_token);
                } else {
                    write_http_response(&mut stream, "404 Not Found", "text/plain", b"Not found")?;
                }
            }
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                thread::sleep(Duration::from_millis(100));
            }
            Err(error) => return Err(error).context("callback server failed"),
        }
    }
}

fn split_http_request(request: &str) -> Result<(&str, &str, &str)> {
    let mut sections = request.splitn(2, "\r\n");
    let status_line = sections.next().unwrap_or_default();
    let remainder = sections.next().unwrap_or_default();
    let mut header_body = remainder.splitn(2, "\r\n\r\n");
    let headers = header_body.next().unwrap_or_default();
    let body = header_body.next().unwrap_or_default();
    if status_line.is_empty() {
        bail!("received malformed HTTP request");
    }
    Ok((status_line, headers, body))
}

fn parse_content_length(headers: &str) -> Option<usize> {
    headers.lines().find_map(|line| {
        let (name, value) = line.split_once(':')?;
        if name.eq_ignore_ascii_case("content-length") {
            value.trim().parse().ok()
        } else {
            None
        }
    })
}

fn write_http_response(
    stream: &mut std::net::TcpStream,
    status: &str,
    content_type: &str,
    body: &[u8],
) -> Result<()> {
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    stream.write_all(response.as_bytes())?;
    stream.write_all(body)?;
    stream.flush()?;
    Ok(())
}

fn callback_page_html(callback_path: &str) -> String {
    format!(
        r#"<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>CLI Login</title></head>
<body>
<p>Completing login...</p>
<script>
const params = new URLSearchParams(window.location.hash.substring(1));
const payload = {{
  id_token: params.get('id_token')
}};
fetch('/token-callback', {{
  method: 'POST',
  headers: {{ 'Content-Type': 'application/json' }},
  body: JSON.stringify(payload)
}}).then(() => {{
  document.body.innerHTML = '<p>Login complete. You can close this tab.</p>';
  window.history.replaceState({{}}, document.title, '{callback_path}');
}}).catch((error) => {{
  document.body.innerHTML = '<p>Login failed: ' + error + '</p>';
}});
</script>
</body>
</html>"#
    )
}

fn success_page_html() -> &'static str {
    "<!DOCTYPE html><html><body><p>Token captured. You can close this tab.</p></body></html>"
}

#[cfg(test)]
mod tests {
    use super::{callback_request_path, redirect_uri_with_port};
    use url::Url;

    #[test]
    fn redirect_uri_with_port_replaces_port_zero_with_assigned_port() {
        let redirect = Url::parse("http://127.0.0.1:0/admin.html").unwrap();
        let redirect = redirect_uri_with_port(redirect, 49152).unwrap();

        assert_eq!(redirect.as_str(), "http://127.0.0.1:49152/admin.html");
    }

    #[test]
    fn callback_request_path_preserves_query_string() {
        let redirect = Url::parse("http://localhost:8000/admin.html?source=cli").unwrap();

        assert_eq!(
            callback_request_path(&redirect),
            "/admin.html?source=cli".to_string()
        );
    }
}
