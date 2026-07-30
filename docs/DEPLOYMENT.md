# Deployment Guide

Comprehensive guide to deploying Muddy's Top 10 Tracker to AWS.

## Architecture Overview

The deployment script handles the following:

1. **SAM Stack Deployment** - Lambda functions, DynamoDB tables, API Gateway
2. **Frontend Configuration** - Injects API endpoint into HTML
3. **S3 Upload** - Uploads configured frontend to S3
4. **CloudFront Setup** - CDN for fast global delivery
5. **Cache Invalidation** - Ensures latest version is served

## Prerequisites

### Required Tools

- AWS CLI (v2.x or later)
- AWS SAM CLI (v1.x or later)
- Bash shell
- Active AWS account with credentials configured

### AWS Permissions Required

The deploying IAM user/role needs permissions for:
- CloudFormation (full)
- Lambda (full)
- DynamoDB (full)
- API Gateway (full)
- S3 (full)
- CloudFront (full)
- IAM (role creation)
- EventBridge (full)

## Quick Deployment

### 1. Pre-flight Check

```bash
./test_deployment.sh
```

This validates:
- AWS CLI installed
- SAM CLI installed
- AWS credentials configured
- Required files present
- SAM template valid

### 2. Deploy

```bash
./deploy.sh --env dev
```

Use the environment name you want to deploy, such as `dev`, `prod`, or
`teleport-dev`.

**First Time For An Environment**: The script prompts for:
- Stack name
- AWS region
- Stream URL
- Optional Spotify client ID/secret
- Whether Spotify validation, OAuth admin UI, and playlist generation should be enabled
- Optional custom CloudFront hostname and us-east-1 ACM certificate ARN

**Subsequent Deployments**: The script reuses the saved `samconfig.toml`
environment unless you choose a new `--env`.

### 3. Wait for Completion

Deployment takes ~5-10 minutes:
- CloudFormation stack creation
- Lambda deployment
- DynamoDB table creation
- CloudFront distribution setup
- Frontend upload

## What the Deploy Script Does

### Step-by-Step Process

```
1. 📦 Build SAM Application
   - Packages Lambda functions
   - Resolves dependencies
   - Prepares artifacts

2. 🚀 Deploy SAM Stack
   - Creates/updates CloudFormation stack
   - Provisions AWS resources
   - Configures permissions
   - Uses containerized SAM builds so the matching local Python runtime is not required

3. 📊 Read Stack Outputs
   - Extracts API Gateway URL
   - Gets S3 bucket name
   - Retrieves CloudFront distribution ID

4. ⚙️  Configure Frontend
   - Reads frontend/index.html
   - Replaces %%API_ENDPOINT%% with actual URL
   - Generates configured HTML

5. 📤 Upload to S3
   - Uploads configured index.html
   - Sets content-type and cache headers
   - Serves through CloudFront OAC

6. 🔄 Invalidate CloudFront
   - Creates invalidation for /*
   - Clears CDN cache
   - Ensures fresh content delivery

7. 🧪 Test Deployment
   - Skip unauthenticated API health check because endpoints require Cognito
   - Verify CloudFront frontend accessibility
   - Report deployed URLs
```

Use named environments for dev/prod deployments:

```bash
./deploy.sh --env dev
./deploy.sh --env prod
```

AgentCore Gateway and AgentCore Memory are required stack resources. New
environments do not prompt whether to enable AgentCore.

Set a custom AgentCore Memory name when needed:

```bash
./deploy.sh --env prod \
  --agentcore-memory-name teleport_prod_agentcore_memory
```

If no memory name is supplied, the deploy script derives one from
`teleport-%ENV%-agentcore-memory`, normalized to underscores because AgentCore
Memory names cannot contain hyphens. Scheduled generation runs as an IAM
workload and uses the same required memory resource.

Configure optional Bedrock-backed campaign generation:

```bash
./deploy.sh --env prod \
  --campaign-model-id deepseek.v3.2 \
  --campaign-model-endpoint bedrock-mantle
```

To route campaign generation through Strands' OpenAI Responses provider for
Mantle, store a Bedrock/Mantle API key in Secrets Manager first. The secret can
be a plain string or JSON containing `api_key`, `bedrock_api_key`, or `key`.

```bash
./deploy.sh --env prod \
  --campaign-model-id deepseek.v3.2 \
  --campaign-model-endpoint strands-openai-responses \
  --campaign-model-api-key-secret-arn arn:aws:secretsmanager:us-west-2:123456789012:secret:my-bedrock-api-key
```

Clear the model settings and use deterministic campaign drafts:

```bash
./deploy.sh --env prod --clear-campaign-model
```

`deepseek.v3.2` on `bedrock-mantle` is the default. If `CampaignModelId`
is blank, no model call is made and campaign generation uses deterministic
fallback. The final infographic HTML/CSS asset is requested as fenced `html`
and `css` blocks, not JSON, to avoid large escaped-code JSON failures.

Direct final PNG generation is configured separately from campaign copy/content
generation because text models such as DeepSeek are not necessarily image
models. When `CampaignImageModelId` is set, campaign generation first attempts
to create the final infographic PNG from the stored template reference PNG plus
the factual chart data. If the image model fails or no template reference PNG
exists, the existing Playwright HTML/CSS renderer is used as fallback.

```bash
./deploy.sh --env prod \
  --campaign-image-model-id IMAGE_MODEL_ID \
  --campaign-image-model-api-key-secret-arn arn:aws:secretsmanager:us-west-2:123456789012:secret:my-image-api-key \
  --campaign-image-size 1280x720
```

If the image model uses the same Mantle/OpenAI-compatible API key as the
campaign model, omit `--campaign-image-model-api-key-secret-arn` and it will
reuse `CampaignModelApiKeySecretArn`.

```bash
./deploy.sh --env prod --clear-campaign-image-model
```

If the environment does not exist in `samconfig.toml`, the script asks one set of setup questions and writes the new SAM config section itself. Dev environments can skip Spotify and custom hostname settings, using the generated CloudFront domain.

Spotify can be explicitly toggled per environment:

```bash
./deploy.sh --env dev --enable-spotify
./deploy.sh --env dev --disable-spotify
```

When disabled, the admin Spotify tab is hidden, Spotify API actions return a
disabled response, the playlist schedule is disabled, and track validation uses
MusicBrainz only.

## Manual Deployment Steps

If you prefer manual control:

### Step 1: Build

```bash
sam build --use-container
```

### Step 2: Deploy Stack

```bash
sam deploy --config-env prod --stack-name teleport-prod-muddys-top-10
```

### Step 3: Get Outputs

```bash
# Get API URL
API_URL=$(aws cloudformation describe-stacks \
    --stack-name teleport-prod-muddys-top-10 \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

# Get S3 bucket
BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name teleport-prod-muddys-top-10 \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
    --output text)
```

### Step 4: Configure Frontend

```bash
sed "s|%%API_ENDPOINT%%|$API_URL|g" \
    frontend/index.html > frontend/index-configured.html
```

### Step 5: Upload to S3

```bash
aws s3 cp frontend/index-configured.html \
    s3://$BUCKET_NAME/index.html \
    --content-type "text/html" \
    --cache-control "max-age=300"
```

### Step 6: Invalidate CloudFront

```bash
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name teleport-prod-muddys-top-10 \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text)

aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*"
```

## Post-Deployment

### Get Your URLs

```bash
aws cloudformation describe-stacks \
    --stack-name teleport-prod-muddys-top-10 \
    --query 'Stacks[0].Outputs'
```

Key outputs:
- `FrontendUrl` - frontend URL, using the custom domain when configured
- `ApiUrl` - API Gateway URL
- `CloudFrontDomainName` - generated CloudFront domain, used as the CNAME target for custom DNS

### Test the Application

1. Open CloudFront URL in browser
2. Wait 2-3 minutes for initial data
3. Check History tab for tracks
4. Check Top 10 tab (may be empty initially)

### Monitor Logs

**Stream Poller:**
```bash
sam logs -n StreamPollerFunction \
    --stack-name teleport-prod-muddys-top-10 \
    --tail
```

**API Handler:**
```bash
sam logs -n ApiFunction \
    --stack-name teleport-prod-muddys-top-10 \
    --tail
```

## Configuration Changes

### Update Stream URL

Edit `samconfig.toml`:

```toml
parameter_overrides = "StreamUrl=http://your-new-url:port/7.html"
```

Then redeploy:

```bash
./deploy.sh --env prod
```

### Update Frontend

Edit `frontend/index.html`, then:

```bash
./deploy.sh --env prod
```

Only frontend upload and CloudFront invalidation will run (fast).

### Update API Code

Edit files in `src/api/` or `src/poller/`, then:

```bash
./deploy.sh --env prod
```

Full stack update will run.

## Troubleshooting

### Deployment Fails

**CloudFormation Error:**
```bash
# View events
aws cloudformation describe-stack-events \
    --stack-name teleport-prod-muddys-top-10 \
    --max-items 20
```

**Permission Denied:**
- Check IAM permissions
- Verify `aws sts get-caller-identity` works

**Template Validation Failed:**
```bash
sam validate --lint
```

### Frontend Not Loading

**Check S3 Upload:**
```bash
aws s3 ls s3://$BUCKET_NAME/
```

**Check S3 Permissions:**
- Bucket policy should allow CloudFront OAC access
- Direct public S3 reads should remain blocked

**Check CloudFront:**
```bash
aws cloudfront get-distribution \
    --id $DISTRIBUTION_ID
```

### API Errors

**Test API Health:**
```bash
curl https://your-api-url/api/health
```

**Check Lambda Logs:**
```bash
sam logs -n ApiFunction \
    --stack-name teleport-prod-muddys-top-10 \
    --tail
```

**Check DynamoDB:**
```bash
aws dynamodb scan \
    --table-name teleport-prod-muddys-top-10-tracks \
    --limit 5
```

### CloudFront Cache Issues

**Force Cache Clear:**
```bash
aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*"
```

**Wait for Invalidation:**
```bash
aws cloudfront get-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --id $INVALIDATION_ID
```

## Updating the Stack

### Minor Updates (Frontend Only)

If you only changed `frontend/index.html`:

```bash
./deploy.sh --env prod
```

This is fast (~1 minute) as it only uploads to S3 and invalidates cache.

### Major Updates (Infrastructure)

If you changed `template.yaml` or Lambda code:

```bash
./deploy.sh --env prod
```

This takes longer (~5-10 minutes) as it updates the CloudFormation stack.

### Update Stack Name

To use a different stack name, create or edit a SAM config environment:

1. Edit `samconfig.toml`:
   ```toml
   [your-env.deploy.parameters]
   stack_name = "your-new-name"
   s3_prefix = "your-new-name"
   ```

2. Deploy:
   ```bash
   ./deploy.sh --env your-env
   ```

## Rollback

### CloudFormation Rollback

AWS automatically rolls back failed deployments.

To manually rollback:

```bash
# Delete current stack
sam delete --stack-name teleport-prod-muddys-top-10

# Redeploy previous version
git checkout <previous-commit>
./deploy.sh --env prod
```

### Frontend Rollback

To revert frontend only:

```bash
# Get previous version of HTML
git checkout HEAD~1 frontend/index.html

# Redeploy
./deploy.sh --env prod
```

## Complete Teardown

To delete everything:

```bash
sam delete --stack-name teleport-prod-muddys-top-10
```

This removes:
- All Lambda functions
- DynamoDB tables (all data lost!)
- API Gateway
- S3 bucket and contents
- CloudFront distribution
- IAM roles
- EventBridge rules

**Note:** CloudFront distribution deletion takes 15-30 minutes.

## Cost Optimization

### Reduce Polling Frequency

Edit `template.yaml`:

```yaml
Events:
  PollerSchedule:
    Type: Schedule
    Properties:
      Schedule: 'rate(5 minutes)'  # Changed from 1 minute
```

### Reduce Data Retention

Edit `src/poller/app.py`:

```python
'ttl': timestamp + (30 * 86400)  # Changed from 90 days
```

### Use Shorter CloudFront Cache

Edit `deploy.sh`:

```bash
--cache-control "max-age=60"  # Changed from 300
```

## Security Hardening

### Enable API Authentication

Add to `template.yaml`:

```yaml
ApiGateway:
  Type: AWS::Serverless::Api
  Properties:
    Auth:
      ApiKeyRequired: true
```

### Restrict CORS

Edit `template.yaml`:

```yaml
Cors:
  AllowOrigin: "'https://yourdomain.com'"
```

### Enable CloudFront HTTPS Only

Already configured - CloudFront redirects HTTP to HTTPS.

### Enable DynamoDB Encryption

Add to `template.yaml`:

```yaml
TracksTable:
  Type: AWS::DynamoDB::Table
  Properties:
    SSESpecification:
      SSEEnabled: true
```

## Custom Domain

To use your own domain:

1. Create or import an ACM certificate in `us-east-1` for the custom domain.
2. Deploy with `CustomDomainName` and `CloudFrontCertificateArn`.
3. Create a DNS CNAME from the custom domain to the `CloudFrontDomainName` stack output. If using Route 53, an alias record to the CloudFront distribution is also valid.
4. Use the `FrontendUrl` stack output as the application URL.

Example:

```bash
sam deploy --parameter-overrides \
  CustomDomainName=top10.example.com \
  CloudFrontCertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: aws-actions/setup-sam@v2
      - uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-west-2
      - run: ./deploy.sh --env prod
```

### AWS CodePipeline

Create pipeline with:
- Source: GitHub/CodeCommit
- Build: CodeBuild (runs deploy.sh)
- Deploy: Manual approval

## Support

For issues or questions:
- Check CloudWatch Logs
- Review CloudFormation events
- See ARCHITECTURE.md for system design
- See README.md for general docs
