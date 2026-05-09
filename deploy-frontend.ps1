# ============================================================================
# Build React Frontend & Deploy to S3 + CloudFront (PowerShell)
# Reads deployment-info.txt for bucket/distribution details
# ============================================================================
$ErrorActionPreference = "Stop"

# Read deployment info
$infoHash = @{}
Get-Content "deployment-info.txt" | ForEach-Object {
    if ($_ -match '^(\w+)=(.+)$') { $infoHash[$matches[1]] = $matches[2] }
}

$S3_BUCKET = $infoHash['S3_BUCKET']
$CF_DIST_ID = $infoHash['CF_DISTRIBUTION_ID']
$CF_DOMAIN = $infoHash['CF_DOMAIN']

if (-not $S3_BUCKET -or -not $CF_DIST_ID) {
    Write-Host "ERROR: Run aws-setup.ps1 first to create deployment-info.txt" -ForegroundColor Red
    exit 1
}

# Build frontend
Write-Host ">>> Building React frontend..." -ForegroundColor Yellow
Push-Location frontend
npm run build
Pop-Location

# Upload to S3
Write-Host ">>> Uploading to S3: $S3_BUCKET..." -ForegroundColor Yellow
aws s3 sync frontend/dist/ "s3://$S3_BUCKET/" `
    --delete `
    --cache-control "public, max-age=31536000" `
    --region ap-south-1

# HTML — no cache
aws s3 cp frontend/dist/index.html "s3://$S3_BUCKET/index.html" `
    --cache-control "public, max-age=0, must-revalidate" `
    --content-type "text/html" `
    --region ap-south-1

# Invalidate CloudFront
Write-Host ">>> Invalidating CloudFront cache..." -ForegroundColor Yellow
aws cloudfront create-invalidation `
    --distribution-id $CF_DIST_ID `
    --paths "/*"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Frontend deployed!" -ForegroundColor Green
Write-Host "  URL: https://$CF_DOMAIN" -ForegroundColor Green
Write-Host "  (may take 5 min for first propagation)" -ForegroundColor Gray
Write-Host "============================================" -ForegroundColor Green
