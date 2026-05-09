#!/bin/bash
# ============================================================================
# InsureRAG — Full AWS Deployment Script
# Region: ap-south-1 (Mumbai)
# ============================================================================
set -e

REGION="ap-south-1"
APP_NAME="insurerag"
KEY_NAME="${APP_NAME}-key"
SG_NAME="${APP_NAME}-sg"
S3_BUCKET="${APP_NAME}-frontend-$(date +%s)"
EC2_INSTANCE_TYPE="t3.medium"
AMI_ID="ami-0f58b397bc5c1f2e8"  # Amazon Linux 2023 ap-south-1

echo "============================================"
echo "  InsureRAG AWS Deployment"
echo "  Region: ${REGION}"
echo "============================================"

# ─── Step 1: Create EC2 Key Pair ─────────────────────────────────────
echo ""
echo ">>> Step 1: Creating EC2 Key Pair..."
aws ec2 create-key-pair \
    --key-name ${KEY_NAME} \
    --query 'KeyMaterial' \
    --output text \
    --region ${REGION} > ${KEY_NAME}.pem 2>/dev/null || echo "Key pair already exists"

chmod 400 ${KEY_NAME}.pem 2>/dev/null || true
echo "    Key saved: ${KEY_NAME}.pem"

# ─── Step 2: Create Security Group ──────────────────────────────────
echo ""
echo ">>> Step 2: Creating Security Group..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region ${REGION})

SG_ID=$(aws ec2 create-security-group \
    --group-name ${SG_NAME} \
    --description "InsureRAG - SSH, HTTP, HTTPS" \
    --vpc-id ${VPC_ID} \
    --query 'GroupId' \
    --output text \
    --region ${REGION} 2>/dev/null || \
    aws ec2 describe-security-groups --group-names ${SG_NAME} --query 'SecurityGroups[0].GroupId' --output text --region ${REGION})

# Allow SSH, HTTP, HTTPS
aws ec2 authorize-security-group-ingress --group-id ${SG_ID} --protocol tcp --port 22 --cidr 0.0.0.0/0 --region ${REGION} 2>/dev/null || true
aws ec2 authorize-security-group-ingress --group-id ${SG_ID} --protocol tcp --port 80 --cidr 0.0.0.0/0 --region ${REGION} 2>/dev/null || true
aws ec2 authorize-security-group-ingress --group-id ${SG_ID} --protocol tcp --port 443 --cidr 0.0.0.0/0 --region ${REGION} 2>/dev/null || true
aws ec2 authorize-security-group-ingress --group-id ${SG_ID} --protocol tcp --port 8000 --cidr 0.0.0.0/0 --region ${REGION} 2>/dev/null || true
echo "    Security Group: ${SG_ID}"

# ─── Step 3: Launch EC2 Instance ─────────────────────────────────────
echo ""
echo ">>> Step 3: Launching EC2 Instance (${EC2_INSTANCE_TYPE})..."

USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
yum update -y
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# Install docker-compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create app directory
mkdir -p /home/ec2-user/app
chown ec2-user:ec2-user /home/ec2-user/app
USERDATA
)

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id ${AMI_ID} \
    --instance-type ${EC2_INSTANCE_TYPE} \
    --key-name ${KEY_NAME} \
    --security-group-ids ${SG_ID} \
    --user-data "${USER_DATA}" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${APP_NAME}-server}]" \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
    --query 'Instances[0].InstanceId' \
    --output text \
    --region ${REGION})

echo "    Instance: ${INSTANCE_ID}"
echo "    Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids ${INSTANCE_ID} --region ${REGION}

# ─── Step 4: Allocate Elastic IP ─────────────────────────────────────
echo ""
echo ">>> Step 4: Allocating Elastic IP..."
ALLOC_ID=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text --region ${REGION})
ELASTIC_IP=$(aws ec2 describe-addresses --allocation-ids ${ALLOC_ID} --query 'Addresses[0].PublicIp' --output text --region ${REGION})
aws ec2 associate-address --instance-id ${INSTANCE_ID} --allocation-id ${ALLOC_ID} --region ${REGION}
echo "    Elastic IP: ${ELASTIC_IP}"

# ─── Step 5: Create S3 Bucket for Frontend ────────────────────────────
echo ""
echo ">>> Step 5: Creating S3 Bucket for Frontend..."
aws s3 mb s3://${S3_BUCKET} --region ${REGION}

# Enable static website hosting
aws s3 website s3://${S3_BUCKET} --index-document index.html --error-document index.html

# Set bucket policy for public read
cat > /tmp/bucket-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::${S3_BUCKET}/*"
        }
    ]
}
EOF

# Disable block public access
aws s3api put-public-access-block \
    --bucket ${S3_BUCKET} \
    --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" \
    --region ${REGION}

aws s3api put-bucket-policy --bucket ${S3_BUCKET} --policy file:///tmp/bucket-policy.json --region ${REGION}
echo "    Bucket: ${S3_BUCKET}"

# ─── Step 6: Create CloudFront Distribution ──────────────────────────
echo ""
echo ">>> Step 6: Creating CloudFront Distribution..."

cat > /tmp/cf-config.json <<EOF
{
    "CallerReference": "${APP_NAME}-$(date +%s)",
    "Comment": "InsureRAG Frontend",
    "DefaultCacheBehavior": {
        "TargetOriginId": "S3-${S3_BUCKET}",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": { "Quantity": 2, "Items": ["HEAD", "GET"] },
        "ForwardedValues": { "QueryString": false, "Cookies": { "Forward": "none" } },
        "MinTTL": 0,
        "DefaultTTL": 86400,
        "MaxTTL": 31536000,
        "Compress": true
    },
    "Origins": {
        "Quantity": 2,
        "Items": [
            {
                "Id": "S3-${S3_BUCKET}",
                "DomainName": "${S3_BUCKET}.s3-website.${REGION}.amazonaws.com",
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only"
                }
            },
            {
                "Id": "EC2-Backend",
                "DomainName": "${ELASTIC_IP}",
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only"
                }
            }
        ]
    },
    "CacheBehaviors": {
        "Quantity": 5,
        "Items": [
            {
                "PathPattern": "/api/*",
                "TargetOriginId": "EC2-Backend",
                "ViewerProtocolPolicy": "allow-all",
                "AllowedMethods": { "Quantity": 7, "Items": ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"] },
                "ForwardedValues": { "QueryString": true, "Cookies": { "Forward": "all" }, "Headers": { "Quantity": 1, "Items": ["*"] } },
                "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0
            },
            {
                "PathPattern": "/upload/*",
                "TargetOriginId": "EC2-Backend",
                "ViewerProtocolPolicy": "allow-all",
                "AllowedMethods": { "Quantity": 7, "Items": ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"] },
                "ForwardedValues": { "QueryString": true, "Cookies": { "Forward": "all" }, "Headers": { "Quantity": 1, "Items": ["*"] } },
                "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0
            },
            {
                "PathPattern": "/query/*",
                "TargetOriginId": "EC2-Backend",
                "ViewerProtocolPolicy": "allow-all",
                "AllowedMethods": { "Quantity": 7, "Items": ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"] },
                "ForwardedValues": { "QueryString": true, "Cookies": { "Forward": "all" }, "Headers": { "Quantity": 1, "Items": ["*"] } },
                "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0
            },
            {
                "PathPattern": "/summarize-user-doc/*",
                "TargetOriginId": "EC2-Backend",
                "ViewerProtocolPolicy": "allow-all",
                "AllowedMethods": { "Quantity": 7, "Items": ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"] },
                "ForwardedValues": { "QueryString": true, "Cookies": { "Forward": "all" }, "Headers": { "Quantity": 1, "Items": ["*"] } },
                "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0
            },
            {
                "PathPattern": "/clear-database/*",
                "TargetOriginId": "EC2-Backend",
                "ViewerProtocolPolicy": "allow-all",
                "AllowedMethods": { "Quantity": 7, "Items": ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"] },
                "ForwardedValues": { "QueryString": true, "Cookies": { "Forward": "all" }, "Headers": { "Quantity": 1, "Items": ["*"] } },
                "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 0
            }
        ]
    },
    "DefaultRootObject": "index.html",
    "Enabled": true,
    "PriceClass": "PriceClass_200"
}
EOF

CF_DIST_ID=$(aws cloudfront create-distribution \
    --distribution-config file:///tmp/cf-config.json \
    --query 'Distribution.Id' \
    --output text 2>/dev/null || echo "PENDING")

CF_DOMAIN=$(aws cloudfront create-distribution \
    --distribution-config file:///tmp/cf-config.json \
    --query 'Distribution.DomainName' \
    --output text 2>/dev/null || echo "PENDING")

echo "    CloudFront ID: ${CF_DIST_ID}"
echo "    CloudFront URL: https://${CF_DOMAIN}"

# ─── Summary ─────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  DEPLOYMENT SUMMARY"
echo "============================================"
echo "  EC2 Instance:  ${INSTANCE_ID}"
echo "  Elastic IP:    ${ELASTIC_IP}"
echo "  S3 Bucket:     ${S3_BUCKET}"
echo "  CloudFront:    https://${CF_DOMAIN}"
echo "  Key Pair:      ${KEY_NAME}.pem"
echo ""
echo "  NEXT STEPS:"
echo "  1. Wait 2-3 min for EC2 to finish setup"
echo "  2. Run: bash deploy-backend.sh ${ELASTIC_IP}"
echo "  3. Run: bash deploy-frontend.sh ${S3_BUCKET} ${CF_DIST_ID}"
echo "============================================"

# Save deployment info
cat > deployment-info.txt <<EOF
EC2_INSTANCE_ID=${INSTANCE_ID}
ELASTIC_IP=${ELASTIC_IP}
S3_BUCKET=${S3_BUCKET}
CF_DISTRIBUTION_ID=${CF_DIST_ID}
CF_DOMAIN=${CF_DOMAIN}
KEY_NAME=${KEY_NAME}
REGION=${REGION}
EOF
echo "Deployment info saved to deployment-info.txt"
