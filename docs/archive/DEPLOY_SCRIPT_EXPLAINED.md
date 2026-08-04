# Deploy Script Explained

Deep dive into what `deploy.sh` does under the hood.

This document lives under `docs/`; links to root deployment files use `../`.

## Script Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      deploy.sh                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 1: Build SAM Application   │
         └──────────────────────────────────┘
                            │
                            ├─ sam build --use-container
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 2: Deploy SAM Stack        │
         └──────────────────────────────────┘
                            │
                            ├─ Check if selected --env exists in samconfig.toml
                            ├─ If yes: sam deploy --config-env <env>
                            └─ If no: prompt, write config, then sam deploy --config-env <env>
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 3: Get Stack Outputs       │
         └──────────────────────────────────┘
                            │
                            ├─ Query CloudFormation for ApiUrl
                            ├─ Query CloudFormation for FrontendBucketName
                            ├─ Query CloudFormation for CloudFrontDistributionId
                            └─ Query CloudFormation for FrontendUrl
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 4: Configure Frontend      │
         └──────────────────────────────────┘
                            │
                            ├─ Read frontend/index.html
                            ├─ Replace %%API_ENDPOINT%% with ApiUrl
                            └─ Write to frontend/index-configured.html
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 5: Upload to S3            │
         └──────────────────────────────────┘
                            │
                            ├─ aws s3 cp index-configured.html
                            ├─ Set content-type: text/html
                            └─ Set cache-control: max-age=300
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 6: Update Cognito URLs     │
         └──────────────────────────────────┘
                            │
                            └─ aws cognito-idp update-user-pool-client
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 7: Invalidate CloudFront   │
         └──────────────────────────────────┘
                            │
                            └─ aws cloudfront create-invalidation --paths "/*"
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 8: Test Deployment         │
         └──────────────────────────────────┘
                            │
                            └─ curl CloudFront frontend URL
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  Step 9: Display Summary         │
         └──────────────────────────────────┘
                            │
                            ├─ Show all URLs
                            ├─ Show useful commands
                            └─ Cleanup temp files
                            │
                            ▼
                          DONE ✅
```

## Step-by-Step Breakdown

### Step 1: Build SAM Application

```bash
sam build --use-container
```

**What it does:**
- Reads `template.yaml`
- Packages Lambda functions in `src/poller/` and `src/api/`
- Builds inside the Lambda runtime container, so the matching local Python runtime is not required
- Packages Lambda layer in `layers/common/`
- Resolves Python dependencies from `requirements.txt`
- Creates `.aws-sam/build/` directory with artifacts
- Prepares deployment package

**Duration:** ~30 seconds

**Output:**
```
Building codeuri: src/poller runtime: python3.14
Building codeuri: src/api runtime: python3.14
Building layer 'CommonLayer'

Build Succeeded
```

### Step 2: Deploy SAM Stack

```bash
# Using an existing environment
sam deploy --config-env prod --stack-name muddys-now-playing

# Or let the deploy script create/use the environment
./deploy.sh --env prod
```

**What it does:**
- Uploads artifacts to S3 (managed by SAM)
- Creates/updates CloudFormation stack
- Creates all AWS resources:
  - Lambda functions
  - DynamoDB tables
  - API Gateway
  - S3 bucket
  - CloudFront distribution
  - IAM roles
  - EventBridge rules
- Waits for stack completion

**Duration:** ~5-10 minutes (first time), ~2-5 minutes (updates)

**CloudFormation Events:**
```
CREATE_IN_PROGRESS   TracksTable
CREATE_IN_PROGRESS   ConfigTable
CREATE_IN_PROGRESS   StreamPollerFunction
CREATE_IN_PROGRESS   ApiFunction
CREATE_IN_PROGRESS   FrontendBucket
CREATE_IN_PROGRESS   CloudFrontDistribution (longest ~5 min)
...
CREATE_COMPLETE      Stack
```

### Step 3: Get Stack Outputs

```bash
# Get API URL
API_URL=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

# Get S3 bucket name
BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
    --output text)

# Get CloudFront distribution ID
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text)

# Get CloudFront URL
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
    --output text)

# Get raw CloudFront domain name for custom DNS CNAME targets
CLOUDFRONT_DOMAIN_NAME=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomainName`].OutputValue' \
    --output text)
```

**What it does:**
- Queries CloudFormation stack outputs
- Extracts critical values needed for configuration
- Keeps both the active frontend URL and the raw CloudFront domain available when a custom CNAME is configured
- Validates that all required outputs exist
- Exits with error if outputs are missing

**Duration:** ~2 seconds

**Example Output:**
```
API URL: https://abc123xyz.execute-api.us-east-1.amazonaws.com/Prod/api
S3 Bucket: muddys-now-playing-frontend-123456789012
CloudFront Distribution: E1ABCDEFGHIJK
```

### Step 4: Configure Frontend

```bash
sed "s|%%API_ENDPOINT%%|$API_URL|g" \
    frontend/index.html > frontend/index-configured.html
```

**What it does:**
- Reads `frontend/index.html`
- Finds the placeholder: `const API_BASE = '%%API_ENDPOINT%%';`
- Replaces it with actual API URL
- Writes configured HTML to temporary file

**Duration:** <1 second

**Before:**
```javascript
const API_BASE = '%%API_ENDPOINT%%';
```

**After:**
```javascript
const API_BASE = 'https://abc123xyz.execute-api.us-east-1.amazonaws.com/Prod/api';
```

**Why this matters:**
- Frontend needs to know where the API is
- API URL is dynamic (changes per deployment)
- Automated injection eliminates manual configuration
- Makes deployment fully hands-off

### Step 5: Upload to S3

```bash
aws s3 cp frontend/index-configured.html \
    s3://$BUCKET_NAME/index.html \
    --content-type "text/html" \
    --cache-control "max-age=300"
```

**What it does:**
- Uploads configured HTML to S3 bucket
- Sets correct MIME type for browser rendering
- Sets cache duration (300 seconds = 5 minutes)
- Serves the file through CloudFront OAC

**Duration:** <1 second

**S3 Object Properties:**
- Key: `index.html`
- Content-Type: `text/html`
- Cache-Control: `max-age=300`
- Private S3 bucket access through CloudFront OAC

**Why cache-control matters:**
- Browsers cache for 5 minutes (performance)
- Short enough for quick updates
- Long enough to reduce requests

### Step 7: Invalidate CloudFront Cache

```bash
aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*"
```

**What it does:**
- Tells CloudFront to clear its cache
- Ensures latest version is served globally
- Creates invalidation request
- Returns invalidation ID

**Duration:**
- Command: <1 second
- Propagation: 1-3 minutes globally

**Why this is critical:**
- CloudFront caches content at edge locations
- Without invalidation, users see old version
- Invalidation forces CDN to fetch fresh content
- Applies to all paths (`/*`)

**Cost:** First 1,000 invalidations/month are free

### Step 8: Test Deployment

```bash
# Test CloudFront
curl -L -s -o /dev/null -w "%{http_code}" "$CLOUDFRONT_URL/"
```

**What it does:**
- Skips unauthenticated API health checks because API endpoints require Cognito
- Tests the CloudFront frontend URL is reachable
- Validates HTTP status codes

**Duration:** ~2 seconds

**Success Indicators:**
- CloudFront returns HTTP 200

### Step 9: Display Summary

```bash
echo "Frontend URL:     $CLOUDFRONT_URL"
echo "API Endpoint:     $API_URL"
echo "S3 Bucket:        $BUCKET_NAME"
```

**What it does:**
- Shows all important URLs
- Displays useful commands
- Provides next steps
- Cleans up temporary files

## Error Handling

### API URL Not Retrieved

**Error:**
```
❌ Error: Could not retrieve API URL from stack outputs
```

**Cause:**
- Stack deployment failed
- Stack doesn't exist
- Wrong stack name

**Fix:**
```bash
# Check stack status
aws cloudformation describe-stacks --stack-name muddys-now-playing

# View events
aws cloudformation describe-stack-events \
    --stack-name muddys-now-playing --max-items 20
```

### S3 Upload Failed

**Error:**
```
upload failed: ... Access Denied
```

**Cause:**
- Insufficient permissions
- Bucket doesn't exist
- Bucket in different region

**Fix:**
```bash
# Check bucket exists
aws s3 ls | grep muddys-now-playing

# Check bucket region
aws s3api get-bucket-location \
    --bucket $BUCKET_NAME
```

### CloudFront Invalidation Failed

**Error:**
```
An error occurred (NoSuchDistribution)
```

**Cause:**
- Distribution not fully created
- Wrong distribution ID
- Distribution in different account

**Fix:**
```bash
# List distributions
aws cloudfront list-distributions \
    --query 'DistributionList.Items[].{Id:Id,DomainName:DomainName}'

# Wait for distribution to complete
aws cloudfront wait distribution-deployed \
    --id $DISTRIBUTION_ID
```

## Variables Used

| Variable | Source | Example |
|----------|--------|---------|
| `STACK_NAME` | Script constant | `muddys-now-playing` |
| `API_URL` | CloudFormation output | `https://abc.execute-api.us-east-1.amazonaws.com/Prod/api` |
| `BUCKET_NAME` | CloudFormation output | `muddys-now-playing-frontend-123456789012` |
| `DISTRIBUTION_ID` | CloudFormation output | `E1ABCDEFGHIJK` |
| `CLOUDFRONT_URL` | CloudFormation output | `https://d1234abcd.cloudfront.net` |

## Dependencies

The script requires:
- `bash` - Shell
- `sam` - AWS SAM CLI
- `aws` - AWS CLI
- `sed` - Text replacement
- `curl` - Testing (optional)

## Debugging

### Verbose Mode

Add to top of script:
```bash
set -x  # Print commands as they execute
```

### Check Each Step

Run steps manually:
```bash
# Step 1
sam build --use-container

# Step 2
sam deploy --config-env prod --stack-name muddys-now-playing

# Step 3
aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs'

# etc...
```

### Check CloudFormation

```bash
# View stack
aws cloudformation describe-stacks \
    --stack-name muddys-now-playing

# View events (last 20)
aws cloudformation describe-stack-events \
    --stack-name muddys-now-playing \
    --max-items 20

# View resources
aws cloudformation describe-stack-resources \
    --stack-name muddys-now-playing
```

## Performance

Typical execution times:

| Step | First Deploy | Update |
|------|--------------|--------|
| 1. Build | 30s | 30s |
| 2. Deploy | 8-10 min | 2-5 min |
| 3. Get outputs | 2s | 2s |
| 4. Configure | <1s | <1s |
| 5. Upload S3 | <1s | <1s |
| 6. Invalidate | <1s | <1s |
| 7. Test | 2s | 2s |
| **Total** | **9-11 min** | **3-6 min** |

**Note:** CloudFront distribution creation (first deploy) takes ~5-7 minutes

## Security

The script:
- ✅ Uses AWS credentials from environment/config
- ✅ Does not hardcode secrets
- ✅ Sets secure S3 permissions via template
- ✅ Uses CloudFront OAC for S3 access
- ✅ Does not expose internal details

## Customization

### Change Stack Name

Edit in script and samconfig.toml:
```bash
STACK_NAME="your-custom-name"
```

### Change Region

Edit `samconfig.toml`:
```toml
region = "eu-west-1"
```

### Skip CloudFront Invalidation

Comment out Step 6:
```bash
# aws cloudfront create-invalidation ...
```

### Add Post-Deploy Actions

Add at end of script:
```bash
# Custom actions
echo "Sending notification..."
curl -X POST https://hooks.slack.com/... \
    -d '{"text":"Deployment complete!"}'
```

## Best Practices

1. **Always run `test_deployment.sh` first**
2. **Review changes before confirming**
3. **Monitor CloudFormation events during deployment**
4. **Save CloudFront URL for future reference**
5. **Test application after deployment**
6. **Check logs if anything fails**

## See Also

- [DEPLOYMENT.md](DEPLOYMENT.md) - Full deployment guide
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [template.yaml](../template.yaml) - Infrastructure definition
- [samconfig.toml](../samconfig.toml) - SAM configuration
