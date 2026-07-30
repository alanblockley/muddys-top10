# Cognito Authentication Setup

The admin panel (`/admin.html`) is protected by AWS Cognito authentication with a hosted UI.

## How It Works

- **Protected**: Top 10 view, history view, filters, chart config, and Spotify admin actions require authentication
- **Protected endpoints**:
  - `GET /api/top10` - requires authentication
  - `GET /api/top10/history` - requires authentication
  - `GET /api/top10/history/{week_id}` - requires authentication
  - `GET /api/config` - requires authentication
  - `GET /api/health` - requires authentication
  - `GET /api/history` - requires authentication
  - `PUT /api/config` - requires authentication
  - `GET /api/spotify/connect` - requires authentication
  - `GET /api/spotify/status` - requires authentication
  - `POST /api/spotify/generate-playlist` - requires authentication
  - `POST /api/spotify/disconnect` - requires authentication
  - `GET /api/campaigns` - requires authentication
  - `GET /api/campaigns/{week_id}` - requires authentication
  - `POST /api/campaigns/generate` - requires authentication
  - `PUT /api/campaigns/{week_id}` - requires authentication
  - `PUT /api/campaigns/{week_id}/status` - requires authentication
- **Technical callback**: `GET /api/spotify/callback` remains reachable for Spotify OAuth completion
- **Admin UI**: Cognito hosted UI provides login/signup flow
- **Token-based**: JWT tokens authorize API requests

Scheduled campaign draft generation is not a Cognito user action. It runs under
the `CampaignGeneratorFunction` IAM role via EventBridge.

## First-Time Setup

After deployment, create your first admin user:

```bash
# Get User Pool ID from stack outputs
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

# Create admin user
aws cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username admin@example.com \
    --user-attributes \
        Name=email,Value=admin@example.com \
        Name=email_verified,Value=true \
    --temporary-password "TempPassword123!" \
    --message-action SUPPRESS
```

**Important**: Replace `admin@example.com` with your actual email address.

## First Login

1. Navigate to `https://your-cloudfront-url/admin.html`
2. Click "Sign In"
3. Enter your email and temporary password
4. You'll be prompted to set a new permanent password
5. After setting password, you'll be redirected back to admin panel

## Password Requirements

- Minimum 8 characters
- Must contain:
  - Uppercase letter
  - Lowercase letter
  - Number

## Managing Users

### Create Additional Users

```bash
aws cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username newadmin@example.com \
    --user-attributes \
        Name=email,Value=newadmin@example.com \
        Name=email_verified,Value=true
```

User will receive an email with temporary password (if email is configured) or you can set it:

```bash
aws cognito-idp admin-set-user-password \
    --user-pool-id $USER_POOL_ID \
    --username newadmin@example.com \
    --password "NewPassword123!" \
    --permanent
```

### Delete User

```bash
aws cognito-idp admin-delete-user \
    --user-pool-id $USER_POOL_ID \
    --username admin@example.com
```

### Reset Password

```bash
aws cognito-idp admin-reset-user-password \
    --user-pool-id $USER_POOL_ID \
    --username admin@example.com
```

### List All Users

```bash
aws cognito-idp list-users \
    --user-pool-id $USER_POOL_ID \
    --query 'Users[*].[Username,UserStatus,Attributes[?Name==`email`].Value|[0]]' \
    --output table
```

## Hosted UI Customization

The Cognito hosted UI domain is automatically created as:
```
https://muddys-now-playing-{account-id}.auth.{region}.amazoncognito.com
```

To customize the UI:

1. Go to AWS Console → Cognito → User Pools
2. Select your pool: `muddys-now-playing-users`
3. App integration → Domain
4. Customize the hosted UI appearance under "App client settings"

## Self-Service Signup

By default, self-signup is disabled. To enable it:

1. AWS Console → Cognito → User Pools → `muddys-now-playing-users`
2. Sign-up experience
3. Enable "Allow users to sign themselves up"
4. Configure email verification settings

Or via CLI:

```bash
aws cognito-idp update-user-pool \
    --user-pool-id $USER_POOL_ID \
    --user-pool-add-ons AdvancedSecurityMode=OFF \
    --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=false}"
```

## Troubleshooting

### "Invalid redirect URI" Error

If you see this error, the callback URL needs to be updated:

```bash
CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text)

CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name muddys-now-playing \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
    --output text)

aws cognito-idp update-user-pool-client \
    --user-pool-id $USER_POOL_ID \
    --client-id $CLIENT_ID \
    --callback-urls "${CLOUDFRONT_URL}/index.html" "${CLOUDFRONT_URL}/admin.html" "http://localhost:8000/index.html" "http://localhost:8000/admin.html" \
    --logout-urls "${CLOUDFRONT_URL}/index.html" "${CLOUDFRONT_URL}/admin.html" "http://localhost:8000/index.html" "http://localhost:8000/admin.html"
```

### Token Expired

JWT tokens expire after 1 hour. If you get authentication errors, sign out and sign back in.

### Can't Access Admin Panel

1. Verify Cognito is deployed:
   ```bash
   aws cognito-idp describe-user-pool --user-pool-id $USER_POOL_ID
   ```

2. Check CloudFront has admin.html:
   ```bash
   curl -I https://your-cloudfront-url/admin.html
   ```

3. Verify API Gateway authorizer:
   ```bash
   aws apigateway get-authorizers \
       --rest-api-id $(aws cloudformation describe-stacks \
           --stack-name muddys-now-playing \
           --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
           --output text | cut -d'/' -f3 | cut -d'.' -f1)
   ```

## Security Notes

- Tokens are stored in browser localStorage
- Logout clears the token
- API Gateway validates tokens on each request
- User Pool enforces password policies
- Failed login attempts are rate-limited by Cognito

## Testing Locally

To test with localhost:

1. Ensure callback URLs include `http://localhost:8000/admin.html`
2. Serve frontend locally:
   ```bash
   cd frontend
   python3 -m http.server 8000
   ```
3. Open `http://localhost:8000/admin.html`

The Cognito client is configured with both CloudFront and localhost callback URLs for `index.html` and `admin.html`.
