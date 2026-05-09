# Medical Summary App - Complete AWS Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Medical Summary Application to AWS with Groq-based consensus system for multi-agent analysis and decision-making.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Cloud                                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐    ┌──────────────┐                   │
│  │  EC2 Instance    │    │  RDS         │                   │
│  │  (Django App)    │───→│  PostgreSQL  │                   │
│  │  + Gunicorn      │    │  Database    │                   │
│  │  + Nginx         │    └──────────────┘                   │
│  │  + Groq Consensus│                                        │
│  └────────┬─────────┘                                        │
│           │                                                  │
│           ↓                                                  │
│  ┌──────────────────────────────────┐                       │
│  │     S3 Bucket                    │                       │
│  │ - Documents                      │                       │
│  │ - Uploads                        │                       │
│  │ - Consensus Results              │                       │
│  │ - Backups                        │                       │
│  └──────────────────────────────────┘                       │
│           ↓                                                  │
│  ┌──────────────────────────────────┐                       │
│  │     Groq API                     │                       │
│  │ (Multi-Agent Consensus)          │                       │
│  └──────────────────────────────────┘                       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Required AWS Services
- AWS Account with billing enabled
- EC2 (t3.medium minimum)
- RDS (PostgreSQL 15.4)
- S3 Bucket
- IAM User with appropriate permissions

### Required API Keys
- Groq API Key (from https://console.groq.com)
- AWS Access Key ID and Secret Key

### Local Tools
- Python 3.9+
- Git
- AWS CLI (optional but recommended)
- pip/virtualenv

## Step 1: Prepare Your Environment

### 1.1 Clone/Download Repository
```bash
cd c:\Users\prath\Downloads\medical-summary-app
```

### 1.2 Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

### 1.3 Install Dependencies
```bash
pip install -r requirements.txt
```

### 1.4 Configure Environment Variables
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual values
# IMPORTANT: Use your actual AWS credentials and Groq API key
```

**Key environment variables to set:**
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
GROQ_API_KEY=your_groq_api_key
S3_BUCKET_NAME=your-unique-bucket-name
RDS_DB_PASSWORD=your_secure_password
```

## Step 2: Create AWS IAM User and Credentials

### 2.1 Create IAM User
1. Go to AWS Console → IAM → Users → Create User
2. Name: `medical-app-deployment`
3. Check "Provide user access to the AWS Management Console"

### 2.2 Attach Policies
Attach the following policies to the user:
- `AmazonEC2FullAccess`
- `AmazonRDSFullAccess`
- `AmazonS3FullAccess`
- `IAMFullAccess` (for security groups)

### 2.3 Create Access Keys
1. User details → Security credentials → Create access key
2. Choose "Command Line Interface (CLI)"
3. Save the Access Key ID and Secret Access Key
4. Add these to your `.env` file

## Step 3: Configure AWS Credentials Locally

### Option A: Using AWS CLI
```bash
aws configure
# Enter your Access Key ID
# Enter your Secret Access Key
# Default region: us-east-1
# Default output format: json
```

### Option B: Using Environment Variables
```bash
set AWS_ACCESS_KEY_ID=your_access_key
set AWS_SECRET_ACCESS_KEY=your_secret_key
```

## Step 4: Verify AWS Configuration
```bash
python -c "
import boto3
client = boto3.client('s3')
response = client.list_buckets()
print('AWS connection successful!')
print('Existing buckets:', [b['Name'] for b in response['Buckets']])
"
```

## Step 5: Deploy to AWS

### 5.1 Run Deployment Script
```bash
python deploy_to_aws.py
```

This script will:
1. Create S3 bucket and folder structure
2. Upload application files to S3
3. Create RDS PostgreSQL database
4. Create EC2 instance with auto-setup
5. Generate deployment configuration
6. Save deployment report

### 5.2 Monitor Deployment
The deployment process takes 5-10 minutes. Watch for:
- ✓ S3 setup completed
- ✓ RDS setup completed (may show "5-10 minutes to become available")
- ✓ EC2 setup completed
- ✓ Configuration generated

### 5.3 Deployment Report
After successful deployment, check:
- `deployment_report_YYYYMMDD_HHMMSS.json` (local)
- `s3://your-bucket-name/deployments/` (S3)

## Step 6: Configure EC2 Instance

### 6.1 SSH into EC2 Instance
```bash
ssh -i your-key-pair.pem ubuntu@your-ec2-public-ip
```

### 6.2 Set Environment Variables
```bash
cd /opt/medical-app
sudo nano .env
# Add your GROQ_API_KEY and other secrets
```

### 6.3 Verify Application is Running
```bash
# Check Gunicorn
sudo supervisorctl status medical-app

# Check Nginx
sudo nginx -t
sudo systemctl status nginx

# View logs
sudo tail -f /var/log/medical-app.out.log
```

## Step 7: Initialize Django Database

### 7.1 SSH into EC2 and Run Migrations
```bash
cd /opt/medical-app
source venv/bin/activate

# Apply Django migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

## Step 8: Test Application

### 8.1 Access Web Interface
Open browser and go to:
```
http://your-ec2-public-ip
```

### 8.2 Test Groq Consensus
```bash
# Test consensus system
curl -X POST http://your-ec2-public-ip/api/consensus/ \
  -d "query=Should a 45-year-old with diabetes be covered?" \
  -d "context=Standard health insurance policy"
```

### 8.3 Upload Test Document
1. Navigate to `/insurance/` endpoint
2. Upload a sample insurance PDF
3. Check consensus results

## Step 9: Enable HTTPS/SSL

### 9.1 Install Let's Encrypt Certificate
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain-name.com
```

### 9.2 Update Django Settings
In `server/core/settings.py`:
```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

## Step 10: Monitoring and Maintenance

### 10.1 Monitor Application
```bash
# CloudWatch Logs
aws logs tail /aws/rds/instance/medical-app-db --follow

# S3 Usage
aws s3 ls s3://your-bucket-name/ --recursive --summarize
```

### 10.2 Backup Database
```bash
# Create snapshot
aws rds create-db-snapshot \
  --db-instance-identifier medical-app-db \
  --db-snapshot-identifier medical-app-backup-$(date +%Y%m%d)
```

### 10.3 Update Application
```bash
# SSH to instance
ssh -i your-key.pem ubuntu@your-ip

# Pull latest code
cd /opt/medical-app
git pull origin main

# Restart application
sudo supervisorctl restart medical-app
```

## Groq Consensus System Integration

### How It Works
1. **Multi-Agent Analysis**: 4 agents (Analyzer, Validator, Critic, Synthesizer)
2. **Iterative Consensus**: Agents debate up to 5 rounds
3. **Confidence Scoring**: 0-1 confidence in final decision
4. **Automatic Persistence**: Results saved to S3

### Using Consensus API

#### Single Query
```python
from groq_consensus import GroqConsensusSystem

system = GroqConsensusSystem(num_agents=4, max_rounds=5)
result = system.reach_consensus(
    context="Insurance policy details...",
    query="Should this patient be covered?"
)

print(f"Decision: {result.final_decision}")
print(f"Confidence: {result.confidence_score}")
print(f"Rounds needed: {result.negotiation_rounds}")
```

#### Batch Processing
```bash
curl -X POST http://your-ip/api/batch-consensus/ \
  -H "Content-Type: application/json" \
  -d '{
    "context": "Insurance policy...",
    "queries": [
      "Is diabetes covered?",
      "What about surgery costs?",
      "Medication coverage details?"
    ]
  }'
```

## Troubleshooting

### Common Issues

#### 1. AWS Credentials Not Working
```bash
# Verify credentials
aws sts get-caller-identity

# If fails, re-configure
aws configure
```

#### 2. S3 Bucket Already Exists
```bash
# Use different bucket name in .env
S3_BUCKET_NAME=your-app-bucket-$(date +%s)
```

#### 3. RDS Connection Timeout
- Wait 5-10 minutes for RDS to fully initialize
- Check security group allows inbound on port 5432
- Verify connection string in EC2 .env

#### 4. Groq API Rate Limits
```python
# Add delays between requests
import time
time.sleep(1)  # 1 second delay
```

#### 5. EC2 Instance Not Starting
- Check AWS EC2 console for errors
- Verify IAM user has EC2 permissions
- Check available resources/quotas

### Debug Commands

```bash
# Check EC2 instance status
aws ec2 describe-instance-status --instance-ids i-xxxxx

# Check RDS status
aws rds describe-db-instances --db-instance-identifier medical-app-db

# Check S3 bucket
aws s3 ls s3://your-bucket-name/

# View EC2 logs
aws ec2 get-console-output --instance-id i-xxxxx
```

## Cost Estimation

### Monthly Costs (Approximate)
- **EC2 t3.medium**: ~$30/month
- **RDS db.t3.micro**: ~$20/month
- **S3 Storage**: ~$0.50-$5/month (depending on data)
- **Data Transfer**: ~$0.50-$2/month
- **Groq API**: Based on usage (free tier available)

**Total: ~$50-$60/month**

## Security Best Practices

### 1. Rotate Credentials Regularly
```bash
# Rotate IAM access keys every 90 days
aws iam create-access-key --user-name medical-app-deployment
aws iam delete-access-key --user-name medical-app-deployment --access-key-id XXXXX
```

### 2. Enable S3 Versioning
Already enabled in deployment script

### 3. Enable RDS Backup
Already enabled (30-day retention)

### 4. Use Secrets Manager for Sensitive Data
```bash
aws secretsmanager create-secret \
  --name medical-app/groq-api-key \
  --secret-string "your-groq-key"
```

### 5. Enable CloudTrail Logging
```bash
aws cloudtrail create-trail \
  --name medical-app-trail \
  --s3-bucket-name your-cloudtrail-bucket
```

## Next Steps

1. Set up custom domain (Route 53)
2. Configure email notifications (SES)
3. Set up CI/CD pipeline (CodePipeline)
4. Implement automated backups
5. Set up monitoring dashboards (CloudWatch)
6. Configure auto-scaling groups

## Support and Resources

- [AWS Documentation](https://docs.aws.amazon.com/)
- [Django Documentation](https://docs.djangoproject.com/)
- [Groq API Documentation](https://console.groq.com/docs)
- [LangChain Documentation](https://python.langchain.com/)

## Notes

- Always use `.env` for sensitive data, never commit it
- Keep `requirements.txt` updated with `pip freeze`
- Monitor AWS costs in AWS Billing console
- Set up cost alerts in AWS Budgets
- Regularly backup your database
- Test disaster recovery procedures

---

**Last Updated**: 2024
**Version**: 1.0
