# ============================================================================
# InsureRAG — Full AWS Deployment (PowerShell)
# Region: ap-south-1 (Mumbai)
# ============================================================================
$ErrorActionPreference = "Continue"
$env:AWS_PAGER = ""

$REGION = "ap-south-1"
$APP_NAME = "insurerag"
$KEY_NAME = "$APP_NAME-key"
$SG_NAME = "$APP_NAME-sg"
$TIMESTAMP = [int](Get-Date -UFormat %s)
$S3_BUCKET = "$APP_NAME-frontend-$TIMESTAMP"
$EC2_INSTANCE_TYPE = "t3.micro"
$AMI_ID = "ami-0f58b397bc5c1f2e8"  # Amazon Linux 2023 ap-south-1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  InsureRAG AWS Deployment" -ForegroundColor Cyan
Write-Host "  Region: $REGION" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# ─── Step 1: Create EC2 Key Pair ─────────────────────────────────────
Write-Host "`n>>> Step 1: Creating EC2 Key Pair..." -ForegroundColor Yellow
try {
    $keyMaterial = aws ec2 create-key-pair --key-name $KEY_NAME --query 'KeyMaterial' --output text --region $REGION 2>$null
    if ($keyMaterial) {
        $keyMaterial | Out-File -FilePath "$KEY_NAME.pem" -Encoding ascii -NoNewline
        Write-Host "    Key saved: $KEY_NAME.pem" -ForegroundColor Green
    }
} catch {
    Write-Host "    Key pair already exists" -ForegroundColor Gray
}

# ─── Step 2: Create Security Group ──────────────────────────────────
Write-Host "`n>>> Step 2: Creating Security Group..." -ForegroundColor Yellow
$VPC_ID = aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region $REGION

# Try to create, or get existing
$SG_ID = aws ec2 create-security-group --group-name $SG_NAME --description "InsureRAG - SSH HTTP HTTPS" --vpc-id $VPC_ID --query 'GroupId' --output text --region $REGION 2>$null
if (-not $SG_ID -or $SG_ID -eq "None") {
    $SG_ID = aws ec2 describe-security-groups --group-names $SG_NAME --query 'SecurityGroups[0].GroupId' --output text --region $REGION
}

# Allow ingress (ignore errors if rules already exist)
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0 --region $REGION 2>$null | Out-Null
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $REGION 2>$null | Out-Null
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0 --region $REGION 2>$null | Out-Null
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 8000 --cidr 0.0.0.0/0 --region $REGION 2>$null | Out-Null
Write-Host "    Security Group: $SG_ID" -ForegroundColor Green

# ─── Step 3: Launch EC2 Instance ─────────────────────────────────────
Write-Host "`n>>> Step 3: Launching EC2 Instance ($EC2_INSTANCE_TYPE)..." -ForegroundColor Yellow

$USER_DATA = @"
#!/bin/bash
yum update -y
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-`$(uname -s)-`$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
mkdir -p /home/ec2-user/app
chown ec2-user:ec2-user /home/ec2-user/app
"@

# Encode user data as base64
$USER_DATA_B64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($USER_DATA))

$INSTANCE_ID = aws ec2 run-instances `
    --image-id $AMI_ID `
    --instance-type $EC2_INSTANCE_TYPE `
    --key-name $KEY_NAME `
    --security-group-ids $SG_ID `
    --user-data $USER_DATA_B64 `
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$APP_NAME-server}]" `
    --block-device-mappings '[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":30,\"VolumeType\":\"gp3\"}}]' `
    --query 'Instances[0].InstanceId' `
    --output text `
    --region $REGION

Write-Host "    Instance: $INSTANCE_ID" -ForegroundColor Green
Write-Host "    Waiting for instance to be running..." -ForegroundColor Gray
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION

# ─── Step 4: Allocate Elastic IP ─────────────────────────────────────
Write-Host "`n>>> Step 4: Allocating Elastic IP..." -ForegroundColor Yellow
$ALLOC_ID = aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text --region $REGION
$ELASTIC_IP = aws ec2 describe-addresses --allocation-ids $ALLOC_ID --query 'Addresses[0].PublicIp' --output text --region $REGION
aws ec2 associate-address --instance-id $INSTANCE_ID --allocation-id $ALLOC_ID --region $REGION | Out-Null
Write-Host "    Elastic IP: $ELASTIC_IP" -ForegroundColor Green

# ─── Step 5: Create S3 Bucket for Frontend ────────────────────────────
Write-Host "`n>>> Step 5: Creating S3 Bucket ($S3_BUCKET)..." -ForegroundColor Yellow
aws s3 mb "s3://$S3_BUCKET" --region $REGION

# Enable static website hosting
aws s3 website "s3://$S3_BUCKET" --index-document index.html --error-document index.html

# Disable block public access
aws s3api put-public-access-block `
    --bucket $S3_BUCKET `
    --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" `
    --region $REGION

# Set bucket policy
$bucketPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "PublicReadGetObject",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::$S3_BUCKET/*"
    }]
}
"@
$bucketPolicy | Out-File -FilePath "$env:TEMP\bucket-policy.json" -Encoding utf8
aws s3api put-bucket-policy --bucket $S3_BUCKET --policy "file://$env:TEMP\bucket-policy.json" --region $REGION
Write-Host "    Bucket: $S3_BUCKET" -ForegroundColor Green

# ─── Step 6: Create CloudFront Distribution ──────────────────────────
Write-Host "`n>>> Step 6: Creating CloudFront Distribution..." -ForegroundColor Yellow

$cfConfig = @"
{
    "CallerReference": "$APP_NAME-$TIMESTAMP",
    "Comment": "InsureRAG Frontend + API Proxy",
    "DefaultCacheBehavior": {
        "TargetOriginId": "S3-$S3_BUCKET",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {"Quantity": 2, "Items": ["HEAD", "GET"]},
        "ForwardedValues": {"QueryString": false, "Cookies": {"Forward": "none"}},
        "MinTTL": 0, "DefaultTTL": 86400, "MaxTTL": 31536000, "Compress": true
    },
    "Origins": {
        "Quantity": 2,
        "Items": [
            {
                "Id": "S3-$S3_BUCKET",
                "DomainName": "$S3_BUCKET.s3-website.$REGION.amazonaws.com",
                "CustomOriginConfig": {"HTTPPort": 80, "HTTPSPort": 443, "OriginProtocolPolicy": "http-only"}
            },
            {
                "Id": "EC2-Backend",
                "DomainName": "$ELASTIC_IP",
                "CustomOriginConfig": {"HTTPPort": 80, "HTTPSPort": 443, "OriginProtocolPolicy": "http-only"}
            }
        ]
    },
    "CacheBehaviors": {
        "Quantity": 5,
        "Items": [
            {"PathPattern": "/api/*", "TargetOriginId": "EC2-Backend", "ViewerProtocolPolicy": "allow-all", "AllowedMethods": {"Quantity": 7, "Items": ["HEAD","DELETE","POST","GET","OPTIONS","PUT","PATCH"]}, "ForwardedValues": {"QueryString": true, "Cookies": {"Forward": "all"}, "Headers": {"Quantity": 1, "Items": ["*"]}}, "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0},
            {"PathPattern": "/upload/*", "TargetOriginId": "EC2-Backend", "ViewerProtocolPolicy": "allow-all", "AllowedMethods": {"Quantity": 7, "Items": ["HEAD","DELETE","POST","GET","OPTIONS","PUT","PATCH"]}, "ForwardedValues": {"QueryString": true, "Cookies": {"Forward": "all"}, "Headers": {"Quantity": 1, "Items": ["*"]}}, "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0},
            {"PathPattern": "/query/*", "TargetOriginId": "EC2-Backend", "ViewerProtocolPolicy": "allow-all", "AllowedMethods": {"Quantity": 7, "Items": ["HEAD","DELETE","POST","GET","OPTIONS","PUT","PATCH"]}, "ForwardedValues": {"QueryString": true, "Cookies": {"Forward": "all"}, "Headers": {"Quantity": 1, "Items": ["*"]}}, "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0},
            {"PathPattern": "/summarize-user-doc/*", "TargetOriginId": "EC2-Backend", "ViewerProtocolPolicy": "allow-all", "AllowedMethods": {"Quantity": 7, "Items": ["HEAD","DELETE","POST","GET","OPTIONS","PUT","PATCH"]}, "ForwardedValues": {"QueryString": true, "Cookies": {"Forward": "all"}, "Headers": {"Quantity": 1, "Items": ["*"]}}, "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0},
            {"PathPattern": "/clear-database/*", "TargetOriginId": "EC2-Backend", "ViewerProtocolPolicy": "allow-all", "AllowedMethods": {"Quantity": 7, "Items": ["HEAD","DELETE","POST","GET","OPTIONS","PUT","PATCH"]}, "ForwardedValues": {"QueryString": true, "Cookies": {"Forward": "all"}, "Headers": {"Quantity": 1, "Items": ["*"]}}, "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0}
        ]
    },
    "DefaultRootObject": "index.html",
    "Enabled": true,
    "PriceClass": "PriceClass_200"
}
"@
$cfConfig | Out-File -FilePath "$env:TEMP\cf-config.json" -Encoding utf8
$cfResult = aws cloudfront create-distribution --distribution-config "file://$env:TEMP\cf-config.json" --output json 2>$null | ConvertFrom-Json
$CF_DIST_ID = $cfResult.Distribution.Id
$CF_DOMAIN = $cfResult.Distribution.DomainName
Write-Host "    CloudFront ID: $CF_DIST_ID" -ForegroundColor Green
Write-Host "    CloudFront URL: https://$CF_DOMAIN" -ForegroundColor Green

# ─── Save deployment info ─────────────────────────────────────────────
$deployInfo = @"
EC2_INSTANCE_ID=$INSTANCE_ID
ELASTIC_IP=$ELASTIC_IP
S3_BUCKET=$S3_BUCKET
CF_DISTRIBUTION_ID=$CF_DIST_ID
CF_DOMAIN=$CF_DOMAIN
KEY_NAME=$KEY_NAME
REGION=$REGION
"@
$deployInfo | Out-File -FilePath "deployment-info.txt" -Encoding utf8

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT SUMMARY" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  EC2 Instance:  $INSTANCE_ID" -ForegroundColor White
Write-Host "  Elastic IP:    $ELASTIC_IP" -ForegroundColor White
Write-Host "  S3 Bucket:     $S3_BUCKET" -ForegroundColor White
Write-Host "  CloudFront:    https://$CF_DOMAIN" -ForegroundColor White
Write-Host "  Key Pair:      $KEY_NAME.pem" -ForegroundColor White
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Wait 2-3 min for EC2 docker to install" -ForegroundColor Gray
Write-Host "  2. Run: .\deploy-backend.ps1" -ForegroundColor Gray
Write-Host "  3. Run: .\deploy-frontend.ps1" -ForegroundColor Gray
Write-Host "============================================" -ForegroundColor Cyan
