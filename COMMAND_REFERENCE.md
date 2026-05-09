# 🚀 Command Reference Card

## Quick Commands

### Initial Setup
```bash
# Setup environment
python manage_app.py setup

# Setup Django
python manage_app.py setup-django

# Check system status
python manage_app.py status
```

---

## Deployment Commands

### AWS Deployment
```bash
# Deploy to AWS (10-15 minutes)
python deploy_to_aws.py

# Dry run (check without deploying)
python manage_app.py deploy-aws --dry-run
```

### Docker Deployment
```bash
# Start all services
docker-compose up -d

# Apply migrations
docker-compose exec app python manage.py migrate

# Create superuser
docker-compose exec app python manage.py createsuperuser

# Stop services
docker-compose down

# View logs
docker-compose logs -f
```

### Local Development
```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run Django server
python server/manage.py runserver

# Run migrations
python server/manage.py migrate

# Create superuser
python server/manage.py createsuperuser
```

---

## Testing Commands

```bash
# Test Groq API
python manage_app.py test-groq

# Test AWS connection
python manage_app.py test-aws

# Run all tests
python test_suite.py

# Run specific test
python -m pytest test_suite.py::TestGroqConsensusSystem -v

# Run Django tests
python server/manage.py test
```

---

## AWS Management Commands

```bash
# Check AWS credentials
aws sts get-caller-identity

# List EC2 instances
aws ec2 describe-instances

# SSH to EC2 instance
ssh -i key-pair.pem ubuntu@public-ip

# View RDS status
aws rds describe-db-instances

# List S3 buckets
aws s3 ls

# View logs
aws logs tail /aws/rds/instance/medical-app-db --follow
```

---

## Groq Consensus Testing

```bash
# Python test (interactive)
python
>>> from groq_consensus import GroqConsensusSystem
>>> system = GroqConsensusSystem(num_agents=4, max_rounds=5)
>>> result = system.reach_consensus("Policy context", "Your question?")
>>> print(result.final_decision)

# REST API test
curl -X POST http://your-server/api/consensus/ \
  -d "query=Your question?" \
  -d "context=Policy details"

# Batch test
curl -X POST http://your-server/api/batch-consensus/ \
  -H "Content-Type: application/json" \
  -d '{"context":"Policy","queries":["Q1?","Q2?"]}'
```

---

## Database Commands

```bash
# Connect to database
psql -h endpoint -U admin -d medicalapp

# Django shell
python server/manage.py shell

# Export data
python server/manage.py dumpdata > data.json

# Import data
python server/manage.py loaddata data.json

# Create backup
pg_dump -h endpoint -U admin medicalapp > backup.sql
```

---

## Monitoring & Logs

```bash
# Docker logs
docker-compose logs -f app           # App logs
docker-compose logs -f db            # Database logs
docker-compose logs -f nginx         # Web server logs

# Linux logs
tail -f /var/log/medical-app.out.log
tail -f /var/log/nginx/medical-app-access.log

# AWS CloudWatch
aws logs tail /aws/rds/instance/medical-app-db --follow

# System info
docker stats
docker ps
df -h
free -h
```

---

## File Management

```bash
# Generate config
python manage_app.py config

# Clean temporary files
python manage_app.py cleanup
python manage_app.py cleanup --target=pyc

# Show structure
tree -L 3

# Find files
find . -name "*.py" -type f
grep -r "error" . --include="*.py"
```

---

## Django Admin

```bash
# Create superuser
python server/manage.py createsuperuser

# Change password
python server/manage.py changepassword username

# Collect static files
python server/manage.py collectstatic

# Check deployment readiness
python server/manage.py check --deploy

# Run migrations
python server/manage.py migrate
python server/manage.py makemigrations
```

---

## Docker Cheat Sheet

```bash
# Image commands
docker build -t medical-app:latest .
docker images
docker rmi image-id

# Container commands
docker run -p 8000:8000 medical-app:latest
docker ps
docker ps -a
docker stop container-id
docker rm container-id

# Compose commands
docker-compose build
docker-compose up -d
docker-compose down
docker-compose ps
docker-compose logs -f
docker-compose exec app bash

# Cleanup
docker prune
docker volume prune
```

---

## Virtual Environment

```bash
# Create
python -m venv venv

# Activate
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Deactivate
deactivate

# Freeze dependencies
pip freeze > requirements.txt

# Install from requirements
pip install -r requirements.txt

# Update single package
pip install --upgrade package-name
```

---

## Environment Configuration

```bash
# Copy template
cp .env.example .env

# Edit configuration
nano .env  # Linux/Mac
notepad .env  # Windows

# Verify keys set
echo $GROQ_API_KEY
echo $AWS_ACCESS_KEY_ID

# Test API key
python -c "from groq import Groq; Groq(api_key='$GROQ_API_KEY').messages.create(...)"
```

---

## Troubleshooting Quick Fixes

```bash
# Port already in use
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Database connection failed
psql -h endpoint -U admin -d medicalapp
# If fails, check RDS status in AWS Console

# API key not working
python manage_app.py test-groq

# AWS credentials issue
aws configure
aws sts get-caller-identity

# Permission denied
sudo chown -R $USER:$USER /opt/medical-app
chmod -R 755 /opt/medical-app

# Docker issues
docker system prune
docker-compose build --no-cache
docker volume prune
```

---

## Performance Optimization

```bash
# Check resource usage
docker stats
htop  # or top

# Database query analysis
\dt  # in psql
\timing on  # Enable timing in psql

# Python profiling
python -m cProfile manage_app.py

# Django debug toolbar
pip install django-debug-toolbar
# Add to INSTALLED_APPS and MIDDLEWARE

# Stress testing
ab -n 1000 -c 10 http://localhost:8000/
```

---

## Backup & Recovery

```bash
# Database backup
pg_dump -h endpoint -U admin medicalapp > backup.sql

# Database restore
psql -h endpoint -U admin medicalapp < backup.sql

# AWS backup
aws rds create-db-snapshot \
  --db-instance-identifier medical-app-db \
  --db-snapshot-identifier medical-app-backup-$(date +%Y%m%d)

# S3 backup
aws s3 sync s3://medical-app-bucket ./backup/ --recursive
```

---

## Deployment Automation

```bash
# Run full setup
python manage_app.py setup && \
python manage_app.py setup-django && \
python manage_app.py test-groq && \
python manage_app.py test-aws

# Deploy and test
python deploy_to_aws.py && \
sleep 300 && \
python manage_app.py test-aws

# Docker full stack
docker-compose up -d && \
docker-compose exec app python manage.py migrate && \
docker-compose logs -f
```

---

## Useful URLs (After Deployment)

```
Home:        http://your-server/
Admin:       http://your-server/admin/
Insurance:   http://your-server/insurance/
API:         http://your-server/api/
Status:      http://your-server/api/consensus-status/
Flower:      http://your-server:5555 (Docker only)
```

---

## Documentation Links

- 📖 [README.md](./README.md) - Overview
- 🚀 [QUICKSTART.md](./QUICKSTART.md) - Quick reference
- 📋 [AWS_DEPLOYMENT_GUIDE.md](./AWS_DEPLOYMENT_GUIDE.md) - Detailed guide
- ✅ [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) - Checklist
- 📊 [DEPLOYMENT_PACKAGE_SUMMARY.md](./DEPLOYMENT_PACKAGE_SUMMARY.md) - Package info

---

## Emergency Contacts

```
AWS Support:     https://console.aws.amazon.com/support
Groq Support:    https://console.groq.com/support
Django Support:  https://docs.djangoproject.com/
GitHub Issues:   [Your repo issues page]
```

---

**Print this card for quick reference during deployment!**

Last updated: 2024
Version: 1.0
