#!/bin/bash
set -e

STACK_NAME="muddys-now-playing"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              Deploying CORS + Theme Updates                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "📦 Building..."
sam build

echo ""
echo "🚀 Deploying stack (API Gateway CORS fix + Lambda updates)..."
sam deploy --stack-name "$STACK_NAME"

echo ""
echo "⏳ Waiting for deployment to complete..."
sleep 5

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
echo "📤 Uploading new themed frontend..."
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
echo "🔄 Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
    --distribution-id "$DIST_ID" \
    --paths "/*" \
    --output text

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Changes:"
echo "  ✓ API Gateway CORS properly configured"
echo "  ✓ OPTIONS handled automatically by API Gateway"
echo "  ✓ Error responses include CORS headers"
echo "  ✓ New warm pub theme applied"
echo ""
echo "🧪 Test CORS:"
echo "  curl -i -H \"Origin: https://example.com\" -H \"Authorization: YOUR_JWT\" $API_URL/health"
echo ""
echo "⏰ Wait 2-3 minutes for CloudFront, then hard refresh your browser!"
echo ""
