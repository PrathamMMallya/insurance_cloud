# ============================================================================
# Deploy Backend to EC2 (PowerShell)
# Reads deployment-info.txt for connection details
# ============================================================================
$ErrorActionPreference = "Stop"

# Read deployment info
$deployInfo = Get-Content "deployment-info.txt" | ForEach-Object {
    $parts = $_ -split '=', 2
    if ($parts.Count -eq 2) { @{ $parts[0].Trim() = $parts[1].Trim() } }
} | ForEach-Object { $_ }

$infoHash = @{}
Get-Content "deployment-info.txt" | ForEach-Object {
    if ($_ -match '^(\w+)=(.+)$') { $infoHash[$matches[1]] = $matches[2] }
}

$ELASTIC_IP = $infoHash['ELASTIC_IP']
$KEY_NAME = $infoHash['KEY_NAME']

if (-not $ELASTIC_IP) {
    Write-Host "ERROR: Run aws-setup.ps1 first to create deployment-info.txt" -ForegroundColor Red
    exit 1
}

Write-Host ">>> Deploying backend to EC2: $ELASTIC_IP" -ForegroundColor Cyan

# Create deployment tarball
Write-Host ">>> Creating deployment package..." -ForegroundColor Yellow
$excludes = @('frontend', 'node_modules', '__pycache__', '.git', 'data', '*.pem', '*.ps1')

# Use tar (available in Windows 10+)
tar czf insurerag-deploy.tar.gz `
    --exclude='frontend' `
    --exclude='node_modules' `
    --exclude='__pycache__' `
    --exclude='.git' `
    --exclude='data' `
    --exclude='*.pem' `
    -C . .

# Upload via SCP
Write-Host ">>> Uploading to EC2..." -ForegroundColor Yellow
scp -i "$KEY_NAME.pem" -o StrictHostKeyChecking=no `
    insurerag-deploy.tar.gz `
    "ec2-user@${ELASTIC_IP}:/home/ec2-user/"

# SSH and deploy
Write-Host ">>> Deploying on EC2..." -ForegroundColor Yellow
ssh -i "$KEY_NAME.pem" -o StrictHostKeyChecking=no "ec2-user@$ELASTIC_IP" @"
    cd /home/ec2-user

    # Install Docker if not present (Amazon Linux)
    if ! command -v docker &> /dev/null; then
        sudo yum update -y
        sudo yum install -y docker
        sudo systemctl enable docker
        sudo systemctl start docker
        sudo usermod -aG docker ec2-user
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-Linux-x86_64" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi

    mkdir -p app
    tar xzf insurerag-deploy.tar.gz -C app/
    cd app
    cp .env.production .env
    mkdir -p data/media data/db
    sudo docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
    sudo docker-compose -f docker-compose.prod.yml build --no-cache
    sudo docker-compose -f docker-compose.prod.yml up -d
    echo ''
    echo '>>> Container status:'
    sudo docker-compose -f docker-compose.prod.yml ps
"@

Remove-Item -Force insurerag-deploy.tar.gz -ErrorAction SilentlyContinue
Write-Host "`n>>> Backend deployed! http://$ELASTIC_IP" -ForegroundColor Green
