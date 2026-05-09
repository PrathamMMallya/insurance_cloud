# Quick Start Guide - Medical Summary App with Groq Consensus

## Prerequisites
- Python 3.9+
- AWS Account (with billing enabled)
- Groq API Key
- 15-20 minutes for deployment

## 5-Minute Setup

### 1. Environment Setup
```bash
# Clone/Navigate to project
cd medical-summary-app

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure AWS & Groq
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials:
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# GROQ_API_KEY=your_groq_key
# S3_BUCKET_NAME=unique-bucket-name
```

### 3. Deploy to AWS
```bash
# Run deployment
python deploy_to_aws.py

# Wait 5-10 minutes for resources to be created
# Note the EC2 public IP from the output
```

### 4. Access Application
```
http://your-ec2-public-ip
```

### 5. Test Consensus System
```bash
# Single query
curl -X POST http://your-ec2-public-ip/api/consensus/ \
  -d "query=Is diabetes covered?" \
  -d "context=Standard health policy"

# Or upload insurance PDF at /insurance/ endpoint
```

## Local Development (No AWS)

### Without AWS Deployment
```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure Django
cd server
python manage.py migrate
python manage.py createsuperuser

# Run server
python manage.py runserver

# Access at http://localhost:8000
```

### Test Groq Consensus Locally
```bash
# Ensure GROQ_API_KEY is in .env
python groq_consensus.py
```

## Docker Deployment

### Using Docker Compose (Fastest)
```bash
# Build and start all services
docker-compose up -d

# Apply migrations
docker-compose exec app python manage.py migrate
docker-compose exec app python manage.py createsuperuser

# Access at http://localhost
```

### Using Docker CLI
```bash
# Build image
docker build -t medical-app:latest .

# Run container
docker run -p 8000:8000 \
  --env-file .env \
  --name medical-app \
  medical-app:latest
```

## Key Features

### 1. Groq Multi-Agent Consensus
- 4 specialized agents (Analyzer, Validator, Critic, Synthesizer)
- Iterative debate up to 5 rounds
- Automatic confidence scoring
- Results saved to S3

### 2. AWS Integration
- **S3**: Document and result storage
- **RDS PostgreSQL**: Application database
- **EC2**: Application server
- **Security Groups**: Network security

### 3. Medical Document Processing
- PDF document upload and parsing
- Text extraction and chunking
- Insurance coverage analysis
- Consensus-based decisions

## API Endpoints

### Consensus Processing
```
POST /api/consensus/
Content-Type: application/x-www-form-urlencoded

Parameters:
- query: Insurance question
- context: Policy details
- document_id: (optional) Document ID

Returns:
{
  "success": true,
  "final_decision": "...",
  "confidence_score": 0.85,
  "negotiation_rounds": 3,
  "agent_positions": {...}
}
```

### Batch Processing
```
POST /api/batch-consensus/
Content-Type: application/json

{
  "context": "Policy details...",
  "queries": [
    "Query 1?",
    "Query 2?"
  ]
}

Returns: Array of results
```

### Status Check
```
GET /api/consensus-status/

Returns system status and statistics
```

## Common Tasks

### Upload Insurance Document
```
1. Navigate to /insurance/
2. Click "Upload Document"
3. Select PDF file and enter title
4. System auto-processes with consensus
```

### View Consensus Results
```
GET /api/document/<document_id>/consensus-results/
```

### Export Results
```
POST /api/export/
Parameters:
- format: json, csv, xlsx
- document_id: (optional)
```

### Test Consensus Locally
```python
from groq_consensus import GroqConsensusSystem

system = GroqConsensusSystem(num_agents=4, max_rounds=5)
result = system.reach_consensus(
    context="Insurance policy...",
    query="Is patient covered?"
)

print(f"Decision: {result.final_decision}")
print(f"Confidence: {result.confidence_score}")
```

## Troubleshooting

### AWS Credentials Not Working
```bash
# Test AWS connection
python -c "import boto3; boto3.client('s3').list_buckets()"

# If fails, reconfigure
aws configure
```

### Groq API Errors
```bash
# Check API key
echo $GROQ_API_KEY  # Should show your key

# Test API
python -c "from groq import Groq; c = Groq(); print('Success')"
```

### Database Connection Issues
```bash
# Check database status
aws rds describe-db-instances --db-instance-identifier medical-app-db

# Connect to database
psql -h <endpoint> -U admin -d medicalapp
```

### Instance Not Responding
```bash
# Get instance details
aws ec2 describe-instances --instance-ids i-xxxxx

# SSH into instance
ssh -i key-pair.pem ubuntu@public-ip

# Check application logs
sudo tail -f /var/log/medical-app.out.log
```

## Performance Tips

1. **Increase Consensus Confidence Threshold**
   ```bash
   CONSENSUS_CONFIDENCE_THRESHOLD=0.85
   ```

2. **Reduce Maximum Rounds for Speed**
   ```bash
   CONSENSUS_MAX_ROUNDS=3
   ```

3. **Use RDS Multi-AZ for Reliability**
   (Already enabled in deployment script)

4. **Enable ElastiCache for Caching**
   (Optional, add Redis configuration)

## Cost Optimization

1. **Use Reserved Instances**
   - t3.medium: ~$30/month → ~$20/month

2. **Enable Auto-Scaling**
   - Scale down during off-hours

3. **Use S3 Lifecycle Policies**
   - Archive old documents

4. **Monitor with CloudWatch**
   - Set up billing alerts

## Security Checklist

- [ ] Change RDS password
- [ ] Enable S3 encryption
- [ ] Configure security group restrictions
- [ ] Enable SSL/TLS (Let's Encrypt)
- [ ] Set strong Django SECRET_KEY
- [ ] Rotate AWS access keys quarterly
- [ ] Enable CloudTrail logging
- [ ] Configure VPC properly

## Next Steps

1. **Customize for Your Use Case**
   - Modify consensus agents for your domain
   - Add custom document processors
   - Create domain-specific prompts

2. **Set Up Monitoring**
   - CloudWatch dashboards
   - Email notifications
   - Cost alerts

3. **Implement CI/CD**
   - GitHub Actions
   - CodePipeline
   - Automated testing

4. **Scale Application**
   - Add RDS read replicas
   - Enable CloudFront CDN
   - Load balancing

## Documentation

- [Full AWS Deployment Guide](./AWS_DEPLOYMENT_GUIDE.md)
- [Groq API Docs](https://console.groq.com/docs)
- [Django Docs](https://docs.djangoproject.com/)
- [LangChain Docs](https://python.langchain.com/)

## Support

For issues:
1. Check error logs
2. Review documentation
3. Test components individually
4. Verify AWS credentials
5. Check API keys are valid

---

**Version**: 1.0
**Last Updated**: 2024
**Status**: Ready for Production
