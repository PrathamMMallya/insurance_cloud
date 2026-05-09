#!/bin/bash
# ============================================================================
# Build React Frontend & Deploy to S3 + Invalidate CloudFront
# Usage: bash deploy-frontend.sh <S3_BUCKET> <CF_DISTRIBUTION_ID>
# ============================================================================
set -e

S3_BUCKET=$1
CF_DIST_ID=$2

if [ -z "$S3_BUCKET" ] || [ -z "$CF_DIST_ID" ]; then
    echo "Usage: bash deploy-frontend.sh <S3_BUCKET> <CF_DISTRIBUTION_ID>"
    exit 1
fi

echo ">>> Building React frontend..."
cd frontend
npm run build

echo ">>> Uploading to S3: ${S3_BUCKET}..."
aws s3 sync dist/ s3://${S3_BUCKET}/ \
    --delete \
    --cache-control "public, max-age=31536000" \
    --region ap-south-1

# HTML files should not be cached aggressively
aws s3 cp dist/index.html s3://${S3_BUCKET}/index.html \
    --cache-control "public, max-age=0, must-revalidate" \
    --content-type "text/html" \
    --region ap-south-1

echo ">>> Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
    --distribution-id ${CF_DIST_ID} \
    --paths "/*"

echo ""
echo ">>> Frontend deployed!"
echo ">>> CloudFront URL will be available in a few minutes."
