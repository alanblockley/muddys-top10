#!/bin/bash
# Mark a problematic track as validated to skip retry loop

set -e

STACK_NAME="muddys-now-playing"
TABLE_NAME="${STACK_NAME}-tracks"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Mark Track as Validated (Skip Validation)             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ -z "$1" ]; then
    echo "Usage: $0 \"Track Name - Title\""
    echo ""
    echo "Example: $0 \"Toni Basil - Mickey\""
    echo ""
    echo "This will find the most recent occurrence of the track and mark it as validated"
    exit 1
fi

TRACK_NAME="$1"

echo "🔍 Searching for track: $TRACK_NAME"
echo ""

# Query DynamoDB for the track (last 24 hours)
CURRENT_TIME=$(date +%s)
ONE_DAY_AGO=$((CURRENT_TIME - 86400))

echo "📊 Scanning last 24 hours of tracks..."
ITEMS=$(aws dynamodb query \
    --table-name "$TABLE_NAME" \
    --index-name "timestamp-index" \
    --key-condition-expression "pk = :pk AND #ts >= :start_time" \
    --expression-attribute-names '{"#ts":"timestamp"}' \
    --expression-attribute-values "{\":pk\":{\"S\":\"TRACK\"},\":start_time\":{\"N\":\"$ONE_DAY_AGO\"}}" \
    --no-scan-index-forward \
    --output json)

# Find matching tracks
MATCHES=$(echo "$ITEMS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
track_name = '$TRACK_NAME'
matches = []
for item in data.get('Items', []):
    track = item.get('track', {}).get('S', '')
    if track == track_name:
        sk = item.get('sk', {}).get('S', '')
        timestamp = item.get('timestamp', {}).get('N', '')
        matches.append({'sk': sk, 'timestamp': timestamp, 'track': track})

# Sort by timestamp (newest first)
matches.sort(key=lambda x: int(x['timestamp']), reverse=True)

# Print as JSON
print(json.dumps(matches))
")

NUM_MATCHES=$(echo "$MATCHES" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")

if [ "$NUM_MATCHES" = "0" ]; then
    echo "❌ No matches found for: $TRACK_NAME"
    echo ""
    echo "Try:"
    echo "  - Check the track name spelling"
    echo "  - View History in admin panel to find exact name"
    echo "  - Track might be older than 24 hours"
    exit 1
fi

echo "✅ Found $NUM_MATCHES occurrence(s)"
echo ""

# Get the most recent one
SK=$(echo "$MATCHES" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['sk'])")
TIMESTAMP=$(echo "$MATCHES" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['timestamp'])")

# Convert timestamp to human readable
READABLE_TIME=$(date -d "@$TIMESTAMP" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || date -r "$TIMESTAMP" "+%Y-%m-%d %H:%M:%S")

echo "📍 Most recent occurrence:"
echo "   Track: $TRACK_NAME"
echo "   Time: $READABLE_TIME"
echo "   SK: $SK"
echo ""

read -p "Mark this track as validated? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 0
fi

echo "✅ Marking track as validated..."

# Update the item
aws dynamodb update-item \
    --table-name "$TABLE_NAME" \
    --key "{\"pk\":{\"S\":\"TRACK\"},\"sk\":{\"S\":\"$SK\"}}" \
    --update-expression "SET validation_status = :status, validation_confidence = :confidence, canonical_track = :canonical" \
    --expression-attribute-values "{\":status\":{\"S\":\"validated\"},\":confidence\":{\"S\":\"manual\"},\":canonical\":{\"S\":\"$TRACK_NAME\"}}"

echo "✅ Track marked as validated"
echo ""
echo "✅ Done! The validator should stop retrying this track."
echo ""
