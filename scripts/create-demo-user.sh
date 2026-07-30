#!/bin/bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-teleport-prod-muddys-top-10}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-west-2}}"
USERNAME="${DEMO_USERNAME:-demo@example.com}"
PASSWORD="${DEMO_PASSWORD:-DemoPassword123}"
USER_POOL_ID="${USER_POOL_ID:-}"

usage() {
    cat <<EOF
Usage: ./scripts/create-demo-user.sh [options]

Create or update a Cognito demo user with a permanent password and no invite email.

Options:
  -h, --help              Show this help and exit
  --stack-name NAME       CloudFormation/SAM stack name (default: $STACK_NAME)
  --region REGION         AWS region (default: $REGION)
  --user-pool-id ID       Cognito user pool ID; skips CloudFormation lookup
  --username EMAIL        Demo user email/username (default: $USERNAME)
  --password PASSWORD     Permanent password (default: $PASSWORD)

Environment overrides:
  STACK_NAME, AWS_REGION, AWS_DEFAULT_REGION, USER_POOL_ID, DEMO_USERNAME, DEMO_PASSWORD

Password must satisfy the pool policy: at least 8 characters with uppercase,
lowercase, and a number.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help|-help)
            usage
            exit 0
            ;;
        --stack-name)
            STACK_NAME="${2:?Missing value for --stack-name}"
            shift 2
            ;;
        --region)
            REGION="${2:?Missing value for --region}"
            shift 2
            ;;
        --user-pool-id)
            USER_POOL_ID="${2:?Missing value for --user-pool-id}"
            shift 2
            ;;
        --username)
            USERNAME="${2:?Missing value for --username}"
            shift 2
            ;;
        --password)
            PASSWORD="${2:?Missing value for --password}"
            shift 2
            ;;
        *)
            echo "Error: Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if ! command -v aws >/dev/null 2>&1; then
    echo "Error: AWS CLI is not installed or not on PATH" >&2
    exit 1
fi

if [[ -z "$USER_POOL_ID" ]]; then
    echo "Resolving Cognito user pool from stack: $STACK_NAME"
    USER_POOL_ID=$(aws cloudformation describe-stacks \
        --region "$REGION" \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
        --output text)
fi

if [[ -z "$USER_POOL_ID" || "$USER_POOL_ID" == "None" ]]; then
    echo "Error: Could not resolve UserPoolId. Pass --user-pool-id or check stack outputs." >&2
    exit 1
fi

echo "User pool: $USER_POOL_ID"
echo "Demo user: $USERNAME"

if aws cognito-idp admin-get-user \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" >/dev/null 2>&1; then
    echo "User already exists; updating password and verified email attributes."
    aws cognito-idp admin-update-user-attributes \
        --region "$REGION" \
        --user-pool-id "$USER_POOL_ID" \
        --username "$USERNAME" \
        --user-attributes \
            Name=email_verified,Value=true >/dev/null
else
    echo "Creating user with invitation suppressed."
    aws cognito-idp admin-create-user \
        --region "$REGION" \
        --user-pool-id "$USER_POOL_ID" \
        --username "$USERNAME" \
        --user-attributes \
            Name=email,Value="$USERNAME" \
            Name=email_verified,Value=true \
        --temporary-password "$PASSWORD" \
        --message-action SUPPRESS >/dev/null
fi

aws cognito-idp admin-set-user-password \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    --permanent >/dev/null

echo "Demo user is ready to log in."
echo "Username: $USERNAME"
echo "Password: $PASSWORD"
