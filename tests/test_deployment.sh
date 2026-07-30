#!/bin/bash
# Quick test script to verify deployment without actually deploying

STACK_NAME="muddys-now-playing"

echo "Testing deployment readiness..."
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi
echo "✅ AWS CLI found"

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    echo "❌ SAM CLI not found. Please install it first."
    exit 1
fi
echo "✅ SAM CLI found"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Run 'aws configure'"
    exit 1
fi
echo "✅ AWS credentials configured"

# Check frontend file
if [ ! -f "frontend/index.html" ]; then
    echo "❌ Frontend file not found: frontend/index.html"
    exit 1
fi
echo "✅ Frontend file exists"

# Check template
if [ ! -f "template.yaml" ]; then
    echo "❌ SAM template not found: template.yaml"
    exit 1
fi
echo "✅ SAM template exists"

# Test template validation
echo ""
echo "Validating SAM template..."
if sam validate --lint &> /dev/null; then
    echo "✅ SAM template is valid"
else
    echo "❌ SAM template validation failed"
    sam validate --lint
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           ALL CHECKS PASSED - READY TO DEPLOY!                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Run: ./deploy.sh"
echo ""
