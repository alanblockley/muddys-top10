#!/bin/bash
# Quick update script for CORS fix

STACK_NAME="muddys-now-playing"

echo "🔧 Updating API Lambda with CORS fix..."
echo ""

# Build and deploy
echo "Building..."
sam build

echo ""
echo "Deploying..."
sam deploy --stack-name "$STACK_NAME"

echo ""
echo "✅ Update complete!"
echo ""
echo "Test the API:"
echo "  curl -H \"Authorization: YOUR_JWT\" https://YOUR-API-URL/api/health"
echo ""
echo "Clear your browser cache and refresh the page."
