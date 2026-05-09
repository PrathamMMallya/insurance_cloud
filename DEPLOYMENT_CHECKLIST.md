# 📋 Deployment Checklist

## Pre-Deployment Setup

### AWS Account Setup
- [ ] AWS Account created
- [ ] Billing enabled
- [ ] AWS region selected (us-east-1 recommended)
- [ ] IAM user created (`medical-app-deployment`)
- [ ] IAM policies attached (EC2, RDS, S3, IAM)
- [ ] Access keys generated and saved

### Local Environment Setup
- [ ] Python 3.9+ installed
- [ ] Project folder created/cloned
- [ ] Virtual environment created
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` file created from `.env.example`

### API Keys & Credentials
- [ ] AWS Access Key ID obtained
- [ ] AWS Secret Access Key obtained
- [ ] Groq API Key obtained from https://console.groq.com
- [ ] All keys added to `.env` file

---

## Configuration Verification

### AWS Configuration
- [ ] AWS_ACCESS_KEY_ID in .env
- [ ] AWS_SECRET_ACCESS_KEY in .env
- [ ] AWS_REGION set (default: us-east-1)
- [ ] S3_BUCKET_NAME unique (no spaces, lowercase)
- [ ] AWS credentials tested: `aws sts get-caller-identity`

### Groq Configuration
- [ ] GROQ_API_KEY in .env
- [ ] API key tested: `python manage_app.py test-groq`

### Database Configuration
- [ ] RDS_DB_NAME set (default: medicalapp)
- [ ] RDS_DB_USER set (default: admin)
- [ ] RDS_DB_PASSWORD is strong (12+ chars, mixed case)
- [ ] DB_INSTANCE_CLASS appropriate (default: db.t3.micro)

### Django Configuration
- [ ] SECRET_KEY generated (use: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] DEBUG set to False
- [ ] ALLOWED_HOSTS configured for your domain

---

## Deployment Option A: AWS Deployment

### Pre-Deployment
- [ ] All configurations in .env verified
- [ ] AWS credentials tested
- [ ] AWS service limits checked (EC2 instances available)
- [ ] AWS region has EC2, RDS, S3 services available

### During Deployment
- [ ] Run: `python deploy_to_aws.py`
- [ ] Monitor console output for status messages
- [ ] Wait for all 4 steps to complete (5-15 minutes)
  - [ ] Step 1: S3 setup
  - [ ] Step 2: RDS setup (may take 10 minutes)
  - [ ] Step 3: EC2 setup
  - [ ] Step 4: Configuration generation

### Post-Deployment
- [ ] Check `deployment_report_*.json` for details
- [ ] Note EC2 public IP from report
- [ ] Wait 5-10 minutes for RDS to become available
- [ ] Check S3 bucket created
- [ ] Verify EC2 instance running in console

### EC2 Configuration
- [ ] SSH into instance: `ssh -i key.pem ubuntu@public-ip`
- [ ] Set GROQ_API_KEY in `.env`
- [ ] Run migrations: `python manage.py migrate`
- [ ] Create superuser: `python manage.py createsuperuser`
- [ ] Test application: `curl http://public-ip`

### Application Setup
- [ ] Access web interface at `http://public-ip`
- [ ] Login with superuser credentials
- [ ] Upload test insurance document
- [ ] Test consensus query
- [ ] Verify results saved to S3

---

## Deployment Option B: Docker Deployment

### Pre-Deployment
- [ ] Docker installed
- [ ] Docker Compose installed
- [ ] All configurations in .env verified
- [ ] 2GB RAM minimum available

### During Deployment
- [ ] Run: `docker-compose up -d`
- [ ] Wait for all services to start (2-3 minutes)
- [ ] Check services running: `docker-compose ps`

### Post-Deployment
- [ ] Apply migrations: `docker-compose exec app python manage.py migrate`
- [ ] Create superuser: `docker-compose exec app python manage.py createsuperuser`
- [ ] Access at `http://localhost`
- [ ] Check logs: `docker-compose logs -f`

### Service Verification
- [ ] Django app running (port 8000)
- [ ] PostgreSQL available (port 5432)
- [ ] Redis running (port 6379)
- [ ] Nginx serving (ports 80, 443)
- [ ] Flower monitoring (port 5555)

---

## Deployment Option C: Local Development

### Setup
- [ ] Python 3.9+ verified
- [ ] Virtual environment activated
- [ ] Dependencies installed
- [ ] .env configured

### Database Setup
- [ ] Run: `cd server`
- [ ] Run migrations: `python manage.py migrate`
- [ ] Create superuser: `python manage.py createsuperuser`

### Start Application
- [ ] Run: `python manage.py runserver`
- [ ] Access at `http://localhost:8000`
- [ ] Admin interface at `http://localhost:8000/admin`

---

## Testing & Validation

### Consensus System
- [ ] Test Groq connection: `python manage_app.py test-groq`
- [ ] Test AWS connection: `python manage_app.py test-aws`
- [ ] Run test suite: `python test_suite.py`
- [ ] Single consensus query works
- [ ] Batch processing works
- [ ] Results saved to S3 (AWS only)

### Application Features
- [ ] Document upload works
- [ ] Document processing starts
- [ ] Consensus agents debate visible
- [ ] Results display correctly
- [ ] Admin interface accessible
- [ ] API endpoints respond

### Database
- [ ] Tables created
- [ ] Data persists after restart
- [ ] Migrations applied successfully
- [ ] Superuser can login

### API Endpoints
- [ ] `/api/consensus/` returns 200
- [ ] `/api/batch-consensus/` works
- [ ] `/insurance/` page loads
- [ ] `/admin/` accessible
- [ ] `/api/consensus-status/` returns status

---

## Security Verification

### AWS Security
- [ ] Security groups restrict public access appropriately
- [ ] RDS not publicly accessible (or restricted)
- [ ] S3 bucket blocks public access
- [ ] IAM user has minimal required permissions
- [ ] Access keys stored securely (not in code)

### Application Security
- [ ] DEBUG set to False
- [ ] SECRET_KEY is random and strong
- [ ] CSRF protection enabled
- [ ] CORS headers appropriate
- [ ] SQL injection prevention (Django ORM)
- [ ] XSS protection enabled

### SSL/TLS
- [ ] HTTPS working (if using custom domain)
- [ ] Certificate valid (Let's Encrypt)
- [ ] HSTS headers present
- [ ] Secure cookie settings enabled
- [ ] HTTPS redirect working

---

## Performance Verification

### Response Times
- [ ] Home page loads in < 2 seconds
- [ ] API endpoint responds in < 1 second
- [ ] Consensus query completes in 30-120 seconds
- [ ] Batch processing reasonable for size
- [ ] Database queries optimized

### System Resources
- [ ] CPU usage reasonable (< 50% at idle)
- [ ] Memory usage acceptable (< 70%)
- [ ] Disk space adequate (> 10GB free)
- [ ] Network connectivity stable
- [ ] No timeout errors

### Scaling
- [ ] RDS Multi-AZ configured (if production)
- [ ] Auto-scaling configured (if needed)
- [ ] Backup strategy in place
- [ ] Monitoring dashboards setup
- [ ] Alerts configured

---

## Monitoring Setup

### Logging
- [ ] Application logs writing
- [ ] Error logs monitored
- [ ] Access logs accessible
- [ ] Log rotation configured
- [ ] Old logs archived

### Metrics
- [ ] CPU usage monitored
- [ ] Memory usage tracked
- [ ] Database connections monitored
- [ ] API response times tracked
- [ ] Error rates measured

### Alerts
- [ ] High CPU alert configured
- [ ] High memory alert configured
- [ ] Failed API requests alert
- [ ] Database connection alert
- [ ] Disk space alert

---

## Documentation

### Generated Documentation
- [ ] README.md reviewed
- [ ] AWS_DEPLOYMENT_GUIDE.md read
- [ ] QUICKSTART.md bookmarked
- [ ] API_REFERENCE.md available
- [ ] DEPLOYMENT_PACKAGE_SUMMARY.md reviewed

### Custom Documentation
- [ ] Environment variables documented
- [ ] Configuration options noted
- [ ] Custom modifications documented
- [ ] Team documentation created
- [ ] Runbooks written

---

## Post-Deployment Tasks

### Week 1
- [ ] Monitor application for errors
- [ ] Check Groq API usage
- [ ] Review CloudWatch logs
- [ ] Test backup procedures
- [ ] Verify all endpoints working

### Week 2
- [ ] Review consensus accuracy
- [ ] Analyze query patterns
- [ ] Optimize prompts if needed
- [ ] Set up monitoring alerts
- [ ] Document findings

### Month 1
- [ ] Review AWS costs
- [ ] Optimize resource sizes if needed
- [ ] Implement any necessary updates
- [ ] Test disaster recovery
- [ ] Plan scaling strategy

---

## Rollback Procedures

### If AWS Deployment Fails
- [ ] Check AWS Console for errors
- [ ] Review CloudFormation events
- [ ] Delete failed resources
- [ ] Fix issues in .env
- [ ] Restart deployment

### If Application Not Working
- [ ] Check application logs
- [ ] Verify database connectivity
- [ ] Test Groq API connection
- [ ] Check security groups
- [ ] Review error messages

### Emergency Rollback
- [ ] Stop application: `docker-compose down` or `supervisorctl stop medical-app`
- [ ] Restore from database backup
- [ ] Verify data integrity
- [ ] Test application functionality
- [ ] Document what went wrong

---

## Final Sign-Off

### Before Production Release
- [ ] All checklist items marked
- [ ] All tests passing
- [ ] All documentation complete
- [ ] Security audit passed
- [ ] Performance acceptable
- [ ] Monitoring active
- [ ] Team trained
- [ ] Backup verified

### Sign-Off by
- [ ] Development Lead: _____ Date: _____
- [ ] Security Team: _____ Date: _____
- [ ] Operations Lead: _____ Date: _____

### Known Limitations
- RDS Single-AZ in free tier
- EC2 t3.medium for moderate load
- Groq rate limits (30 req/min free tier)
- S3 standard storage class

### Future Improvements
- [ ] Plan database replication
- [ ] Design auto-scaling strategy
- [ ] Implement CDN for static files
- [ ] Add advanced monitoring
- [ ] Design disaster recovery
- [ ] Plan horizontal scaling

---

**Start Date**: ________________  
**Deployment Date**: ________________  
**Go-Live Date**: ________________  

**Notes & Issues**:
```
[Space for notes on deployment issues and resolutions]
```

---

**Deployment Status**: ⚪ Not Started | 🟡 In Progress | 🟢 Complete

**Overall Confidence**: ☆☆☆☆☆ | Risk Level: ________________
