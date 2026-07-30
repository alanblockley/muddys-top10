#!/bin/bash
set -e

STACK_NAME="muddys-now-playing"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Configure Top 10 Filters                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Get API URL
API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

if [ -z "$API_URL" ]; then
    echo "❌ Error: Could not retrieve API URL"
    exit 1
fi

echo "API URL: $API_URL"
echo ""

# Define filter patterns
# Using JSON array of regex patterns
cat > /tmp/filters.json << 'EOF'
{
  "top10_filters": [
    "^Muddy'?s Music Cafe",
    "^Muddy'?s Roadshow",
    "^Send your.*http",
    "https?://",
    "secondlife:///",
    "^MUDDY.*DJ.*on MIC"
  ]
}
EOF

echo "Setting filter patterns:"
echo "  • Muddy's/Muddys Music Cafe (all variations)"
echo "  • Muddy's/Muddys Roadshow (all variations)"
echo "  • Send your ... [URL]"
echo "  • Any track with http:// or https://"
echo "  • Any track with secondlife:/// URLs"
echo "  • DJ announcements (MUDDY's - DJ ... on MIC)"
echo ""

echo "Uploading to API..."
curl -X PUT "$API_URL/config" \
    -H "Content-Type: application/json" \
    -d @/tmp/filters.json \
    -s | jq . || cat

rm /tmp/filters.json

echo ""
echo "✅ Filters configured!"
echo ""
echo "To view current config:"
echo "  curl $API_URL/config | jq ."
echo ""
echo "To test Top 10 (with filters applied):"
echo "  curl $API_URL/top10 | jq ."
echo ""
