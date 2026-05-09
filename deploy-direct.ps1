# ============================================================================
# Deploy Backend to EC2 — Direct (No Docker)
# Installs Python + deps, runs Gunicorn behind screen
# ============================================================================
$ErrorActionPreference = "Stop"
$env:AWS_PAGER = ""

$infoHash = @{}
Get-Content "deployment-info.txt" | ForEach-Object {
    if ($_ -match '^(\w+)=(.+)$') { $infoHash[$matches[1]] = $matches[2] }
}

$ELASTIC_IP = $infoHash['ELASTIC_IP']
$KEY_NAME = $infoHash['KEY_NAME']

Write-Host ">>> Deploying backend (no Docker) to EC2: $ELASTIC_IP" -ForegroundColor Cyan

# Create tarball
Write-Host ">>> Creating deployment package..." -ForegroundColor Yellow
tar czf insurerag-deploy.tar.gz `
    --exclude='frontend' `
    --exclude='node_modules' `
    --exclude='__pycache__' `
    --exclude='.git' `
    --exclude='data' `
    --exclude='*.pem' `
    --exclude='*.ps1' `
    --exclude='*.sh' `
    -C . .

# Upload
Write-Host ">>> Uploading to EC2..." -ForegroundColor Yellow
scp -i "$KEY_NAME.pem" -o StrictHostKeyChecking=no `
    insurerag-deploy.tar.gz `
    "ec2-user@${ELASTIC_IP}:/home/ec2-user/"

# SSH and deploy
Write-Host ">>> Installing & starting on EC2..." -ForegroundColor Yellow
ssh -i "$KEY_NAME.pem" -o StrictHostKeyChecking=no "ec2-user@$ELASTIC_IP" @"
    cd /home/ec2-user

    # Install system dependencies
    sudo yum update -y
    sudo yum install -y python3.11 python3.11-pip python3.11-devel gcc screen

    # Extract app
    rm -rf app
    mkdir -p app
    tar xzf insurerag-deploy.tar.gz -C app/
    cd app

    # Copy production env
    cp .env.production .env

    # Install Python dependencies
    python3.11 -m pip install --user -r requirements.txt

    # Run migrations
    cd server
    python3.11 manage.py migrate --noinput

    # Kill any existing gunicorn
    pkill -f gunicorn 2>/dev/null || true
    sleep 1

    # Start gunicorn in screen session (port 8000, accessible from outside)
    screen -dmS insurerag bash -c 'cd /home/ec2-user/app/server && python3.11 -m gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 300 --access-logfile /home/ec2-user/access.log --error-logfile /home/ec2-user/error.log'

    sleep 2
    echo '>>> Checking if gunicorn is running...'
    if pgrep -f gunicorn > /dev/null; then
        echo '>>> Gunicorn is RUNNING on port 8000'
    else
        echo '>>> ERROR: Gunicorn failed to start. Check /home/ec2-user/error.log'
        tail -20 /home/ec2-user/error.log 2>/dev/null
    fi
"@

Remove-Item -Force insurerag-deploy.tar.gz -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Backend deployed! http://$ELASTIC_IP`:8000" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
