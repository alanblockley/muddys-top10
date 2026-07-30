# Deployment Checklist

Use this checklist to ensure a smooth deployment.

## Pre-Deployment

- [ ] AWS CLI installed and configured
  ```bash
  aws --version
  aws configure list
  ```

- [ ] AWS SAM CLI installed
  ```bash
  sam --version
  ```

- [ ] Docker available for containerized SAM builds
  ```bash
  docker --version
  ```

- [ ] Test stream connectivity
  ```bash
  python3 test_stream.py
  ```

- [ ] Review configuration in `samconfig.toml`
  - Stack name
  - AWS region
  - Stream URL parameter
  - Optional custom CloudFront hostname and ACM certificate ARN

## Deployment

- [ ] Build the application
  ```bash
  sam build --use-container
  ```

- [ ] Validate the template
  ```bash
  sam validate
  ```

- [ ] Deploy to AWS
  ```bash
  ./deploy.sh --env prod
  ```

  For a new environment, the deploy script asks for the stack name, AWS region,
  stream URL, optional Spotify credentials, and optional custom CloudFront
  hostname/ACM certificate. Development environments can leave the custom
  hostname and certificate blank.

## Post-Deployment Verification

- [ ] Get API URL
  ```bash
  sam list stack-outputs --stack-name muddys-top10
  ```

- [ ] Test API endpoint
  ```bash
  curl -H "Authorization: Bearer YOUR_COGNITO_JWT" https://YOUR-CLOUDFRONT-URL/api/history
  ```

- [ ] Check poller logs
  ```bash
  sam logs -n StreamPollerFunction --stack-name muddys-top10 --tail
  ```

- [ ] Wait 5-10 minutes for tracks to accumulate

- [ ] Open frontend in browser
  ```
  https://YOUR-CLOUDFRONT-URL/
  ```

- [ ] Verify unauthenticated users only see the login page

- [ ] Verify History view shows data

- [ ] Verify Top 10 view loads (may be empty initially)

## Configuration

- [ ] Set chart generation time (optional)
  ```bash
  curl -X PUT https://YOUR-API-URL/api/config \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer YOUR_COGNITO_JWT" \
    -d '{"chart_generation": {"hour": 0, "day": "monday"}}'
  ```

- [ ] Verify config saved
  ```bash
  curl -H "Authorization: Bearer YOUR_COGNITO_JWT" https://YOUR-API-URL/api/config
  ```

## Monitoring Setup

- [ ] Check CloudWatch Logs are being created
  - `/aws/lambda/muddys-top10-stream-poller`
  - `/aws/lambda/muddys-top10-api`

- [ ] (Optional) Create CloudWatch alarms
  - Poller Lambda errors
  - API Lambda errors
  - DynamoDB throttling

- [ ] (Optional) Enable API Gateway logging

## Optional Enhancements

- [ ] Configure custom CloudFront domain with `CustomDomainName` and a `us-east-1` ACM certificate ARN
- [ ] Review Cognito users and access
- [ ] Restrict CORS to specific domains
- [ ] Enable DynamoDB point-in-time recovery
- [ ] Set up automated backups
- [ ] Configure CloudWatch dashboards

## Troubleshooting

### Deployment Fails

- Check AWS credentials: `aws sts get-caller-identity`
- Check IAM permissions (need CloudFormation, Lambda, DynamoDB, IAM)
- Review CloudFormation events in AWS Console

### No Tracks Appearing

- Check poller logs: `sam logs -n StreamPollerFunction --tail`
- Verify stream URL is accessible: `python3 test_stream.py`
- Check DynamoDB table has items (AWS Console)

### API Returns 502 Errors

- Check API Lambda logs: `sam logs -n ApiFunction --tail`
- Verify Lambda has DynamoDB permissions
- Check Lambda timeout (increase if needed)

### Frontend Not Loading

- Verify API Gateway URL is correct
- Check browser console for errors
- Verify CORS headers in API response

## Tear Down

When you want to remove everything:

- [ ] Backup any data you want to keep
  ```bash
  aws dynamodb scan --table-name muddys-top10-tracks > backup.json
  ```

- [ ] Delete the stack
  ```bash
  sam delete --stack-name muddys-top10
  ```

- [ ] Verify all resources deleted in AWS Console
  - CloudFormation stack
  - Lambda functions
  - DynamoDB tables
  - API Gateway
  - IAM roles

---

## Quick Reference Commands

```bash
# Build
sam build --use-container

# Deploy
sam deploy --config-env prod

# Get outputs
sam list stack-outputs --stack-name muddys-top10

# View logs (poller)
sam logs -n StreamPollerFunction --stack-name muddys-top10 --tail

# View logs (API)
sam logs -n ApiFunction --stack-name muddys-top10 --tail

# Local testing
sam local invoke StreamPollerFunction
sam local start-api

# Delete stack
sam delete --stack-name muddys-top10
```

## Support

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [DynamoDB Documentation](https://docs.aws.amazon.com/dynamodb/)
- [Project README](README.md)
- [Architecture Docs](ARCHITECTURE.md)
