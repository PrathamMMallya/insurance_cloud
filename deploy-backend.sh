#!/bin/bash
# ============================================================================
# Deploy Backend to EC2
# Usage: bash deploy-backend.sh <ELASTIC_IP>
# ============================================================================
set -e

ELASTIC_IP=$1
KEY_NAME="insurerag-key"

if [ -z "$ELASTIC_IP" ]; then
    echo "Usage: bash deploy-backend.sh <ELASTIC_IP>"
    exit 1
fi

echo ">>> Deploying backend to EC2: ${ELASTIC_IP}"

# Create a tarball of the project (excluding frontend, node_modules)
echo ">>> Creating deployment package..."
tar czf /tmp/insurerag-deploy.tar.gz \
    --exclude='frontend' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='data' \
    --exclude='*.pem' \
    -C . .

# Upload to EC2
echo ">>> Uploading to EC2..."
scp -i ${KEY_NAME}.pem -o StrictHostKeyChecking=no \
    /tmp/insurerag-deploy.tar.gz \
    ec2-user@${ELASTIC_IP}:/home/ec2-user/

# SSH and deploy
echo ">>> SSH into EC2 and deploying..."
ssh -i ${KEY_NAME}.pem -o StrictHostKeyChecking=no ec2-user@${ELASTIC_IP} << 'REMOTE'
    cd /home/ec2-user

    # Extract
    mkdir -p app
    tar xzf insurerag-deploy.tar.gz -C app/
    cd app

    # Copy production env
    cp .env.production .env

    # Create data directories for volumes
    mkdir -p data/media data/db

    # Build and start with Docker Compose
    sudo docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
    sudo docker-compose -f docker-compose.prod.yml build --no-cache
    sudo docker-compose -f docker-compose.prod.yml up -d

    # Check status
    echo ""
    echo ">>> Container status:"
    sudo docker-compose -f docker-compose.prod.yml ps
    echo ""
    echo ">>> Backend deployed successfully!"
REMOTE

echo ""
echo ">>> Backend is live at: http://${ELASTIC_IP}"
rm /tmp/insurerag-deploy.tar.gz
