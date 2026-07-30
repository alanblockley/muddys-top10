#!/bin/bash
set -e

STACK_NAME="muddys-now-playing"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              📻 Updating Frontend Theme Only                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "📊 Getting stack outputs..."
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

if [ -z "$API_URL" ] || [ -z "$BUCKET" ] || [ -z "$DIST_ID" ]; then
    echo "❌ Error: Could not retrieve stack outputs"
    echo "   Make sure the stack '$STACK_NAME' is deployed"
    exit 1
fi

echo "API URL:    $API_URL"
echo "S3 Bucket:  $BUCKET"
echo "CloudFront: $DIST_ID"
echo ""

# Get Cognito outputs for admin.html
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

ENABLE_SPOTIFY=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Parameters[?ParameterKey==`EnableSpotify`].ParameterValue' \
    --output text)

if [ -z "$ENABLE_SPOTIFY" ] || [ "$ENABLE_SPOTIFY" = "None" ]; then
    ENABLE_SPOTIFY="false"
fi

# Configure admin.html if Cognito is configured
if [ -f "frontend/admin.html" ] && [ -n "$USER_POOL_ID" ]; then
    echo "Configuring index.html..."
    sed -e "s|%%API_ENDPOINT%%|$API_URL|g" \
        -e "s|%%USER_POOL_ID%%|$USER_POOL_ID|g" \
        -e "s|%%CLIENT_ID%%|$CLIENT_ID|g" \
        -e "s|%%COGNITO_DOMAIN%%|$COGNITO_DOMAIN|g" \
        -e "s|%%ENABLE_SPOTIFY%%|$ENABLE_SPOTIFY|g" \
        frontend/index.html > /tmp/index-configured.html

    echo "Configuring admin.html..."
    sed -e "s|%%API_ENDPOINT%%|$API_URL|g" \
        -e "s|%%USER_POOL_ID%%|$USER_POOL_ID|g" \
        -e "s|%%CLIENT_ID%%|$CLIENT_ID|g" \
        -e "s|%%COGNITO_DOMAIN%%|$COGNITO_DOMAIN|g" \
        -e "s|%%ENABLE_SPOTIFY%%|$ENABLE_SPOTIFY|g" \
        frontend/admin.html > /tmp/admin-configured.html
else
    sed "s|%%API_ENDPOINT%%|$API_URL|g" frontend/index.html > /tmp/index-configured.html
fi

# Configure data-viewer.html
if [ -f "frontend/data-viewer.html" ]; then
    echo "Configuring data-viewer.html..."
    sed "s|%%API_ENDPOINT%%|$API_URL|g" frontend/data-viewer.html > /tmp/data-viewer-configured.html
fi

echo "📤 Uploading to S3..."
aws s3 cp /tmp/index-configured.html s3://$BUCKET/index.html \
    --content-type "text/html" \
    --cache-control "max-age=300" \
    --metadata-directive REPLACE

if [ -f /tmp/admin-configured.html ]; then
    aws s3 cp /tmp/admin-configured.html s3://$BUCKET/admin.html \
        --content-type "text/html" \
        --cache-control "max-age=300" \
        --metadata-directive REPLACE
    echo "✅ admin.html uploaded"
fi

if [ -f /tmp/data-viewer-configured.html ]; then
    aws s3 cp /tmp/data-viewer-configured.html s3://$BUCKET/data-viewer.html \
        --content-type "text/html" \
        --cache-control "max-age=300" \
        --metadata-directive REPLACE
    echo "✅ data-viewer.html uploaded"
fi

# Upload assets folder if it exists
if [ -d "frontend/assets" ]; then
    echo "📁 Uploading assets..."
    aws s3 sync frontend/assets s3://$BUCKET/assets \
        --cache-control "max-age=31536000" \
        --metadata-directive REPLACE
    echo "✅ Assets uploaded"
fi

rm -f /tmp/index-configured.html /tmp/admin-configured.html /tmp/data-viewer-configured.html

echo ""
echo "🔄 Invalidating CloudFront cache..."
INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id "$DIST_ID" \
    --paths "/*" \
    --query 'Invalidation.Id' \
    --output text)

echo "   Invalidation ID: $INVALIDATION_ID"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  ✅ FRONTEND UPDATED                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "⏰ Wait 2-3 minutes for CloudFront to propagate"
echo "🔄 Then hard refresh your browser (Ctrl+Shift+R or Cmd+Shift+R)"
echo ""
echo "Your app:"
echo "  https://$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
    --output text | sed 's|https://||')"
echo ""
