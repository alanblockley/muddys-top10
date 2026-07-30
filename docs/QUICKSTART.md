# Quick Start Guide

Get Muddy's Top 10 Tracker running in AWS in 5 minutes!

## Step 1: Prerequisites

**Install AWS SAM CLI:**
```bash
# macOS
brew install aws-sam-cli

# Linux
pip install aws-sam-cli

# Windows
choco install aws-sam-cli
```

**Configure AWS credentials:**
```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-west-2`)
- Output format (e.g., `json`)

## Step 2: Test Readiness

```bash
./test_deployment.sh
```

This verifies:
- ✅ AWS CLI installed
- ✅ SAM CLI installed
- ✅ AWS credentials configured
- ✅ Required files present
- ✅ Template valid

## Step 3: Deploy

```bash
./deploy.sh --env dev
```

Use the environment name you want, for example `dev`, `prod`, or
`teleport-dev`.

**New environment?** Answer the deploy script prompts:
- **Stack Name**: accept the generated default or enter your stack name
- **AWS Region**: `us-west-2` or your target region
- **Stream URL**: accept the default or enter a custom stream stats URL
- **Spotify credentials**: leave blank unless playlist generation is needed
- **Custom hostname**: answer `n` for a generated CloudFront domain, or provide a custom domain and us-east-1 ACM certificate ARN

**Already deployed?** It uses your saved config automatically!

The script will:
1. 📦 Build SAM application
2. 🚀 Deploy to AWS (~5-10 minutes)
3. 📊 Extract API and frontend outputs
4. ⚙️  Configure frontend Cognito/API settings
5. 📤 Upload to S3
6. 🔐 Configure Cognito callback/logout URLs
7. 🔄 Invalidate CloudFront cache
8. 🧪 Test frontend accessibility

## Step 4: Get Your URL

The deploy script shows your URLs at the end:

```
Frontend URL:     https://d1234abcd.cloudfront.net
API Endpoint:     https://abcd1234.execute-api.us-west-2.amazonaws.com/Prod/api
```

**Open the Frontend URL in your browser!**

## Step 5: Wait for Data

The first unauthenticated page is the Cognito login flow. Create a Cognito user
if this is a new stack, then sign in from the frontend URL.

The stream poller runs every minute. After 5-10 minutes:
1. Sign in through Cognito
2. Refresh the page
3. Open History to see tracked songs
4. Open Top 10 for the weekly chart (may be empty at first)

## That's It! 🎉

Your serverless Top 10 tracker is now running. It will:
- ✅ Poll the stream every minute
- ✅ Track all played songs
- ✅ Generate weekly Top 10 charts
- ✅ Show history in 2-hour blocks
- ✅ Calculate week-over-week movement

## Next Steps

### View Logs

**Stream Poller:**
```bash
sam logs -n StreamPollerFunction --stack-name muddys-now-playing --tail
```

**API Handler:**
```bash
sam logs -n ApiFunction --stack-name muddys-now-playing --tail
```

### Update Frontend

Edit `frontend/index.html`, then:
```bash
./deploy.sh --env dev
```

### Update Configuration

See the root [README.md](../README.md) for API configuration options.

### Monitor

Check CloudWatch:
```bash
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=muddys-now-playing-stream-poller \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum
```

## Troubleshooting

### "Error: Could not retrieve API URL"

**Cause:** Stack deployment failed

**Fix:**
```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
    --stack-name muddys-now-playing \
    --max-items 20

# Delete and retry if this is a disposable environment
sam delete --stack-name muddys-now-playing
./deploy.sh --env dev
```

### Frontend Shows "Error loading history"

**Cause:** You are not signed in, the API is not responding, or no data exists yet

**Fix:**
1. Confirm you are signed in through Cognito
2. Wait 5-10 minutes for data
3. Check API health with a Cognito JWT:
   ```bash
   curl -H "Authorization: Bearer YOUR_COGNITO_JWT" https://YOUR-API-URL/api/health
   ```
4. Check poller logs:
   ```bash
   sam logs -n StreamPollerFunction --stack-name muddys-now-playing --tail
   ```

### "Access Denied" or Permission Errors

**Cause:** Insufficient AWS permissions

**Fix:**
1. Verify credentials:
   ```bash
   aws sts get-caller-identity
   ```
2. Add required permissions (see [DEPLOYMENT.md](DEPLOYMENT.md))
3. Or use an admin user for initial deployment

### CloudFront Shows Old Version

**Cause:** CDN cache not cleared

**Fix:**
```bash
# Get distribution ID
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text)

# Invalidate cache
aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*"

# Wait 2-3 minutes, then refresh browser
```

## Tear Down

When you're done:

```bash
sam delete --stack-name muddys-now-playing
```

**Warning:** This deletes all data!

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `./test_deployment.sh` | Pre-flight check |
| `./deploy.sh --env dev` | Deploy/update an environment |
| `sam logs -n StreamPollerFunction --tail` | View poller logs |
| `sam logs -n ApiFunction --tail` | View API logs |
| `sam delete --stack-name muddys-now-playing` | Delete everything |

---

**Need More Help?** Check the root [README.md](../README.md) or [DEPLOYMENT.md](DEPLOYMENT.md) for detailed documentation.
