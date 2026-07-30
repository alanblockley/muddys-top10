#!/bin/bash
# Test Spotify API access

CLIENT_ID="aafe2d1f118f4ba09571ee792c7ab31c"
CLIENT_SECRET="b8feafa33360463bb3e865cad9db4fcb"

echo "=== Step 1: Get Access Token ==="
TOKEN_RESPONSE=$(curl -s -X POST "https://accounts.spotify.com/api/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}")

echo "$TOKEN_RESPONSE" | python3 -m json.tool
echo ""

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")

if [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ Failed to get access token"
    exit 1
fi

echo "✅ Got access token: ${ACCESS_TOKEN:0:20}..."
echo ""

echo "=== Step 2: Search for Track ==="
# URL encode the query
QUERY='artist:"HUNTRIX" track:"What It Sounds Like"'
ENCODED_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))")

echo "Query: $QUERY"
echo ""

curl -s -X GET "https://api.spotify.com/v1/search?q=${ENCODED_QUERY}&type=track&limit=10" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Accept: application/json" | python3 -m json.tool

echo ""
echo "=== Test Complete ==="
