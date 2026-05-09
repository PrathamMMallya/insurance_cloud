# ============================================================================
# Update Native Backend on EC2 (PowerShell)
# Reads deployment-info.txt and updates /opt/medical-app without Docker
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
    Write-Host "ERROR: deployment-info.txt is missing required details." -ForegroundColor Red
    exit 1
}

Write-Host ">>> Updating native backend on EC2: $ELASTIC_IP" -ForegroundColor Cyan

# Create deployment tarball
Write-Host ">>> Creating deployment package..." -ForegroundColor Yellow

# Use tar to zip files into the Temp directory to avoid archiving itself
$tarPath = "$env:TEMP\insurerag-deploy.tar.gz"
Remove-Item -Force $tarPath -ErrorAction SilentlyContinue

tar czf $tarPath `
    --exclude='venv' `
    --exclude='frontend' `
    --exclude='node_modules' `
    --exclude='__pycache__' `
    --exclude='.git' `
    --exclude='data' `
    --exclude='*.pem' `
    --exclude='*.ps1' `
    -C . .

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: tar command failed!" -ForegroundColor Red
    exit 1
}

# Upload via SCP
Write-Host ">>> Uploading to EC2..." -ForegroundColor Yellow
scp -i "$KEY_NAME.pem" -o StrictHostKeyChecking=no `
    $tarPath `
    "ubuntu@${ELASTIC_IP}:/home/ubuntu/insurerag-deploy.tar.gz"

# SSH and update
Write-Host ">>> Deploying and updating Python packages on EC2..." -ForegroundColor Yellow
ssh -i "$KEY_NAME.pem" -o StrictHostKeyChecking=no "ubuntu@$ELASTIC_IP" @"
    set -e
    cd /home/ubuntu
    
    # Extract to the native app directory at /opt/medical-app
    sudo tar xzf insurerag-deploy.tar.gz -C /opt/medical-app/
    
    # Fix permissions
    sudo chown -R ubuntu:ubuntu /opt/medical-app
    
    # Enter the directory
    cd /opt/medical-app
    
    # Copy env if needed
    if [ -f .env.production ]; then
        cp .env.production .env
    fi
    
    # Clean up disk space to prevent pip install errors
    echo '>>> Cleaning up disk space...'
    sudo apt-get clean
    rm -rf ~/.cache/pip
    sudo docker system prune -af || true
    sudo journalctl --vacuum-time=1d
    
    # Update python packages in the Linux venv
    echo '>>> Installing dependencies...'
    source venv/bin/activate
    pip install --no-cache-dir -r requirements.txt
    
    # Run migrations
    cd server
    python manage.py migrate
    cd ..
    
    # Restart the application
    echo '>>> Restarting supervisor and nginx...'
    # The supervisor service name might be medical-app based on deploy_to_aws.py
    sudo supervisorctl restart medical-app || true
    sudo systemctl restart nginx
    
    echo '>>> Backend updated successfully!'
"@

Remove-Item -Force $tarPath -ErrorAction SilentlyContinue
Write-Host "`n>>> Update complete! http://$ELASTIC_IP" -ForegroundColor Green
