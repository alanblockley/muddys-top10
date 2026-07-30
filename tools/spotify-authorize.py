#!/usr/bin/env python3
"""
One-time Spotify authorization script to obtain a refresh token.

This script performs the OAuth Authorization Code Flow with PKCE to get
a refresh token that can be used for machine-to-machine playlist creation.

Usage:
    1. Set your Spotify Client ID and Secret as environment variables:
       export SPOTIFY_CLIENT_ID=your_client_id
       export SPOTIFY_CLIENT_SECRET=your_client_secret

    2. Run this script:
       python3 tools/spotify-authorize.py

    3. Follow the browser prompt to authorize the app

    4. Copy the refresh token to AWS Secrets Manager:
       aws secretsmanager create-secret \
         --name muddys-top10-spotify-refresh-token \
         --secret-string '{"refresh_token":"YOUR_REFRESH_TOKEN"}'

Required Spotify App Settings:
    - Redirect URI: http://127.0.0.1:8888/callback
    - Scopes: playlist-modify-public, playlist-modify-private
"""

import os
import sys
import urllib.parse
import urllib.request
import json
import base64
import hashlib
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

# Spotify OAuth endpoints
AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
REDIRECT_URI = 'http://127.0.0.1:8888/callback'

# Global to store the authorization code
auth_code = None
code_verifier = None


def generate_code_verifier():
    """Generate a code verifier for PKCE"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')


def generate_code_challenge(verifier):
    """Generate code challenge from verifier"""
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to receive OAuth callback"""

    def do_GET(self):
        global auth_code

        # Parse query parameters
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #1DB954;">Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
            """)
        elif 'error' in params:
            error = params['error'][0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #ff0000;">Authorization Failed</h1>
                    <p>Error: {error}</p>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
            """.encode())

    def log_message(self, format, *args):
        # Suppress HTTP server logs
        pass


def get_authorization_code(client_id, code_challenge):
    """Start OAuth flow and get authorization code"""
    # Build authorization URL
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': 'playlist-modify-public playlist-modify-private',
        'code_challenge_method': 'S256',
        'code_challenge': code_challenge
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n" + "="*70)
    print("SPOTIFY AUTHORIZATION")
    print("="*70)
    print("\n1. Opening browser for Spotify authorization...")
    print("2. Log in and approve the requested permissions")
    print("3. You'll be redirected back to localhost (this script)\n")

    # Open browser
    webbrowser.open(auth_url)

    # Start local server to receive callback
    print("Waiting for authorization callback on http://127.0.0.1:8888...")
    server = HTTPServer(('127.0.0.1', 8888), CallbackHandler)

    # Handle one request (the callback)
    while auth_code is None:
        server.handle_request()

    server.server_close()
    return auth_code


def exchange_code_for_tokens(client_id, client_secret, code, code_verifier):
    """Exchange authorization code for access and refresh tokens"""
    # Build request body
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': client_id,
        'code_verifier': code_verifier
    }

    # Build authorization header
    credentials = f"{client_id}:{client_secret}"
    credentials_b64 = base64.b64encode(credentials.encode()).decode()

    # Make request
    request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(data).encode(),
        headers={
            'Authorization': f'Basic {credentials_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode())
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"\nError exchanging code for tokens:")
        print(f"Status: {e.code}")
        print(f"Response: {error_body}")
        sys.exit(1)


def main():
    # Get credentials from environment
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        print("\nUsage:")
        print("  export SPOTIFY_CLIENT_ID=your_client_id")
        print("  export SPOTIFY_CLIENT_SECRET=your_client_secret")
        print("  python3 tools/spotify-authorize.py")
        sys.exit(1)

    # Generate PKCE codes
    global code_verifier
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Get authorization code
    code = get_authorization_code(client_id, code_challenge)

    if not code:
        print("\nError: Failed to get authorization code")
        sys.exit(1)

    print("\n✓ Authorization code received")

    # Exchange code for tokens
    print("Exchanging code for tokens...")
    tokens = exchange_code_for_tokens(client_id, client_secret, code, code_verifier)

    if 'refresh_token' not in tokens:
        print("\nError: No refresh token in response")
        print(json.dumps(tokens, indent=2))
        sys.exit(1)

    print("\n✓ Tokens received successfully!")
    print("\n" + "="*70)
    print("REFRESH TOKEN (save this securely)")
    print("="*70)
    print(f"\n{tokens['refresh_token']}\n")

    print("="*70)
    print("NEXT STEPS")
    print("="*70)
    print("\n1. Store the refresh token in AWS Secrets Manager:\n")
    print("   aws secretsmanager create-secret \\")
    print("     --name muddys-top10-spotify-refresh-token \\")
    print(f"     --secret-string '{{\"refresh_token\":\"{tokens['refresh_token']}\"}}'\n")
    print("2. Deploy the updated stack with SAM\n")
    print("3. The playlist generator will run automatically every Saturday at 2am PST\n")


if __name__ == '__main__':
    main()
