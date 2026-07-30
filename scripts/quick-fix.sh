#!/bin/bash
set -e

STACK_NAME="muddys-now-playing"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       Quick Fix: Layer Structure + CORS + Theme               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "📦 Building (layer structure is now fixed)..."
sam build

echo ""
echo "🚀 Deploying..."
sam deploy --stack-name "$STACK_NAME"

echo ""
echo "⏳ Waiting for Lambda to be ready..."
sleep 5

echo ""
echo "📊 Getting outputs..."
API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
    --output text)

DIST_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text)

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text)

COGNITO_DOMAIN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoHostedUIUrl`].OutputValue' \
    --output text)

echo ""
echo "🧪 Testing API..."
echo "Health check now requires Cognito Authorization:"
echo "  curl -H \"Authorization: YOUR_JWT\" $API_URL/health"

echo ""
echo ""
echo "📤 Uploading themed frontend..."
sed -e "s|%%API_ENDPOINT%%|$API_URL|g" \
    -e "s|%%USER_POOL_ID%%|$USER_POOL_ID|g" \
    -e "s|%%CLIENT_ID%%|$CLIENT_ID|g" \
    -e "s|%%COGNITO_DOMAIN%%|$COGNITO_DOMAIN|g" \
    frontend/index.html > /tmp/index-configured.html
aws s3 cp /tmp/index-configured.html s3://$BUCKET/index.html \
    --content-type "text/html" \
    --cache-control "max-age=300"
rm /tmp/index-configured.html

echo ""
echo "🔄 Invalidating CloudFront..."
aws cloudfront create-invalidation \
    --distribution-id "$DIST_ID" \
    --paths "/*" \
    --query 'Invalidation.Id' \
    --output text

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    ✅ ALL FIXES DEPLOYED                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Fixes Applied:"
echo "  ✅ Lambda layer structure (common module import)"
echo "  ✅ CORS headers (API Gateway configuration)"
echo "  ✅ Warm pub theme (frontend styling)"
echo ""
echo "Your API:"
echo "  $API_URL"
echo ""
echo "⏰ Wait 2-3 minutes for CloudFront, then refresh your browser!"
echo "   Use Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)"
echo ""
