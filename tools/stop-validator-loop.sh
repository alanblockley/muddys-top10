#!/bin/bash
# Emergency script to stop validator retry loop

set -e

STACK_NAME="muddys-now-playing"
FUNCTION_NAME="${STACK_NAME}-track-validator"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Stop Validator Retry Loop                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Get the event source mapping UUID
echo "🔍 Finding DynamoDB stream trigger..."
UUID=$(aws lambda list-event-source-mappings \
    --function-name "$FUNCTION_NAME" \
    --query 'EventSourceMappings[0].UUID' \
    --output text)

if [ -z "$UUID" ] || [ "$UUID" = "None" ]; then
    echo "❌ Could not find event source mapping"
    exit 1
fi

echo "📍 Event source mapping UUID: $UUID"
echo ""

# Check current state
CURRENT_STATE=$(aws lambda get-event-source-mapping \
    --uuid "$UUID" \
    --query 'State' \
    --output text)

echo "📊 Current state: $CURRENT_STATE"
echo ""

if [ "$CURRENT_STATE" = "Disabled" ] || [ "$CURRENT_STATE" = "Disabling" ]; then
    echo "⚠️  Stream trigger is already disabled or disabling"
    echo ""
    read -p "Re-enable it now? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "✅ Enabling stream trigger..."
        aws lambda update-event-source-mapping \
            --uuid "$UUID" \
            --enabled
        echo "✅ Stream trigger enabled"
    fi
else
    echo "⚠️  WARNING: This will temporarily stop track validation!"
    echo "   - New tracks will not be validated until you re-enable"
    echo "   - Current retry loop will stop"
    echo "   - You should deploy fixes before re-enabling"
    echo ""
    read -p "Disable the stream trigger? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🛑 Disabling stream trigger..."
        aws lambda update-event-source-mapping \
            --uuid "$UUID" \
            --no-enabled

        echo "✅ Stream trigger disabled"
        echo ""
        echo "📋 Next steps:"
        echo "   1. Wait 2-3 minutes for current executions to finish"
        echo "   2. Deploy fixes: sam build && sam deploy"
        echo "   3. Mark problem track: ./tools/mark-track-validated.sh"
        echo "   4. Re-run this script to re-enable the trigger"
    else
        echo "❌ Cancelled"
    fi
fi

echo ""
