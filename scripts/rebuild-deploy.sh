#!/bin/bash
set -e

STACK_NAME="muddys-now-playing"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Rebuilding with Layer Fix + Deploying                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Clean build directory
echo "🧹 Cleaning build directory..."
rm -rf .aws-sam/build/

# Build everything
echo "📦 Building all functions and layers..."
sam build --use-container 2>&1 | tail -30

echo ""
echo "✅ Build complete. Checking layer structure..."
echo ""
echo "Layer contents:"
find .aws-sam/build/CommonLayer -type f

echo ""
echo "🚀 Deploying to AWS..."
sam deploy --stack-name "$STACK_NAME" --no-confirm-changeset

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Testing Lambda..."
sleep 5

API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

echo "Testing API health endpoint..."
curl -s "$API_URL/health" | jq . || curl -s "$API_URL/health"

echo ""
echo "🎉 All done! Check CloudWatch logs if there are still issues."
