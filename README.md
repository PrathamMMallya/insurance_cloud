# Medical Summary App - AWS Deployment with Groq Consensus

A sophisticated Django application that uses **Groq-powered multi-agent consensus system** to analyze medical documents and insurance policies with competing agents reaching mutual consensus on coverage decisions.

## 🚀 Features

### Core Features
- **Multi-Agent Consensus**: 4 AI agents (Analyzer, Validator, Critic, Synthesizer) debate and reach consensus
- **Medical Document Processing**: Extract, chunk, and analyze insurance PDFs
- **AWS Cloud Deployment**: Complete infrastructure with S3, RDS, EC2
- **Groq Integration**: Advanced LLM using Mixtral-8x7b model
- **Django REST API**: RESTful endpoints for all operations
- **Docker Support**: Containerized deployment with docker-compose

### Groq Consensus Features
- **Iterative Debate**: Up to 5 rounds of agent discussion
- **Confidence Scoring**: 0-1 confidence in final decision
- **Hybrid Retrieval**: Smart document chunk selection
- **Automatic Persistence**: Results saved to AWS S3
- **Batch Processing**: Process multiple queries simultaneously

## 📋 Prerequisites

### Required
- Python 3.9+
- AWS Account (with billing enabled)
- Groq API Key ([free at console.groq.com](https://console.groq.com))
- 20-30 minutes for AWS deployment

### AWS Services Used
- **EC2**: t3.medium instance (~$30/month)
- **RDS**: PostgreSQL database (~$20/month)
- **S3**: Document storage (~$1-5/month)
- **Security Groups**: Network isolation (free)

### Optional
- Docker & Docker Compose (for containerized deployment)
- AWS CLI (for additional management)
- Git (for version control)

## 🎯 Quick Start (5 Minutes)

### Step 1: Setup Environment
```bash
# Navigate to project
cd medical-summary-app

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Credentials
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your values:
nano .env
# Required:
# AWS_ACCESS_KEY_ID=your_aws_key
# AWS_SECRET_ACCESS_KEY=your_aws_secret
# GROQ_API_KEY=your_groq_api_key
# S3_BUCKET_NAME=unique-bucket-name-12345
```

### Step 3: Deploy to AWS
```bash
# Run deployment script
python deploy_to_aws.py

# Wait 5-10 minutes for resources to initialize
# Note: RDS takes 5-10 minutes to become available
```

### Step 4: Access Application
```
http://your-ec2-public-ip
```

## 📦 Installation & Setup

### Option A: AWS Deployment (Production)
See [AWS_DEPLOYMENT_GUIDE.md](./AWS_DEPLOYMENT_GUIDE.md) for detailed instructions.

### Option B: Docker Deployment (Recommended)
```bash
# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Start all services
docker-compose up -d

# Apply migrations
docker-compose exec app python manage.py migrate
docker-compose exec app python manage.py createsuperuser

# Access at http://localhost
```

### Option C: Local Development (No AWS)
```bash
cd server

# Create local database
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Access at http://localhost:8000
```

## 🔌 API Usage

### Single Query with Consensus
```python
from groq_consensus import GroqConsensusSystem

# Initialize system
system = GroqConsensusSystem(
    num_agents=4,          # 4 specialized agents
    max_rounds=5           # Up to 5 debate rounds
)

# Process query
result = system.reach_consensus(
    context="Insurance policy coverage details...",
    query="Is diabetes covered under this plan?"
)

# Results
print(f"Decision: {result.final_decision}")
print(f"Confidence: {result.confidence_score}")      # 0.0-1.0
print(f"Rounds Needed: {result.negotiation_rounds}")  # 1-5
print(f"Agent Positions: {result.agent_positions}")   # Each agent's view
```

### REST API Endpoint
```bash
# Single consensus query
curl -X POST http://your-server/api/consensus/ \
  -d "query=Is diabetes covered?" \
  -d "context=Standard health insurance policy"

# Batch processing
curl -X POST http://your-server/api/batch-consensus/ \
  -H "Content-Type: application/json" \
  -d '{
    "context": "Policy details...",
    "queries": ["Query 1?", "Query 2?", "Query 3?"]
  }'

# System status
curl http://your-server/api/consensus-status/
```

## 📁 Project Structure

```
medical-summary-app/
├── requirements.txt              # Python dependencies
├── deploy_to_aws.py             # AWS deployment script
├── groq_consensus.py            # Groq multi-agent consensus system
├── manage_app.py                # Management utility
├── test_suite.py                # Comprehensive tests
├── Dockerfile                   # Docker image definition
├── docker-compose.yml           # Docker Compose configuration
├── nginx.conf                   # Nginx web server config
├── .env.example                 # Environment template
├── AWS_DEPLOYMENT_GUIDE.md      # Detailed AWS guide
├── QUICKSTART.md                # Quick reference
│
├── server/
│   ├── manage.py               # Django management script
│   ├── core/                   # Django project settings
│   │   ├── settings.py         # Configuration
│   │   ├── urls.py             # URL routing
│   │   └── wsgi.py             # WSGI application
│   │
│   ├── insurance/              # Insurance app
│   │   ├── models.py           # Database models
│   │   ├── views.py            # View logic
│   │   ├── urls.py             # URL patterns
│   │   └── templates/
│   │
│   ├── medical_app/            # Medical app
│   │   ├── models.py
│   │   ├── views.py
│   │   └── templates/
│   │
│   ├── ai_modules/             # AI processing
│   │   ├── insurance_processor.py
│   │   └── summarizer/
│   │
│   └── consensus_views.py      # Consensus API endpoints
│
└── docs/
    ├── API_REFERENCE.md        # API documentation
    └── ARCHITECTURE.md         # System architecture
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         Client/Browser                  │
└─────────────────┬───────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────┐
│     Nginx (Load Balancer/Proxy)         │
└─────────────────┬───────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────┐
│   EC2 Instance (Django + Gunicorn)      │
│  ┌──────────────────────────────────┐  │
│  │  Groq Consensus System           │  │
│  │  - 4 Specialized Agents          │  │
│  │  - Iterative Debate              │  │
│  │  - Confidence Scoring            │  │
│  └──────────────────────────────────┘  │
└─────────────────┬───────────────────────┘
        │         │         │
        ↓         ↓         ↓
    ┌────┐   ┌────┐   ┌────────┐
    │RDS │   │ S3 │   │Groq API│
    │    │   │    │   │        │
    └────┘   └────┘   └────────┘
```

## 🔑 Key Components

### 1. Groq Consensus System
Four specialized agents analyze insurance documents:
- **Analyzer**: Extracts facts and patterns
- **Validator**: Verifies claims and consistency
- **Critic**: Challenges assumptions
- **Synthesizer**: Integrates perspectives

### 2. AWS Infrastructure
- **S3**: Document and result storage
- **RDS PostgreSQL**: Application database
- **EC2**: Application server
- **Security Groups**: Network isolation

### 3. Django Application
- REST API for document upload/analysis
- Admin interface for management
- Database models for persistence
- Template-based web interface

## 🧪 Testing

### Run All Tests
```bash
python test_suite.py
```

### Test Specific Components
```bash
# Test Groq connection
python manage_app.py test-groq

# Test AWS connection
python manage_app.py test-aws

# Test consensus system
python -m pytest test_suite.py::TestGroqConsensusSystem -v
```

## 🚀 Deployment

### Deploy to AWS
```bash
python deploy_to_aws.py
```

### Deploy with Docker
```bash
docker-compose up -d
docker-compose exec app python manage.py migrate
```

### Monitor Deployment
```bash
# Check deployment status
aws ec2 describe-instances --instance-ids i-xxxxx

# View application logs
aws logs tail /aws/rds/instance/medical-app-db --follow

# SSH to instance
ssh -i key-pair.pem ubuntu@public-ip
```

## 📊 Groq Consensus Features

### Agent Debate Process
1. **Round 1**: Initial analysis from all agents
2. **Round 2-5**: Agents evaluate each other's positions
3. **Convergence**: Agents reach consensus on key points
4. **Synthesis**: Final decision integrating all views

### Confidence Scoring
- **0.0-0.4**: Low confidence (agents still disagreeing)
- **0.4-0.7**: Medium confidence (approaching agreement)
- **0.7-1.0**: High confidence (consensus reached)

### Automatic Persistence
- Results saved to S3 automatically
- Stored in `consensus_results/` folder
- JSON format with full agent positions

## 🔒 Security Features

- ✅ SSL/TLS encryption (Let's Encrypt)
- ✅ S3 versioning and encryption
- ✅ RDS backup and recovery
- ✅ Security group isolation
- ✅ IAM role-based access
- ✅ Environment variable secrets
- ✅ CSRF protection
- ✅ SQL injection prevention

## 📈 Performance

### Consensus Processing Time
- **Simple query**: 30-60 seconds
- **Complex query**: 60-120 seconds
- **Batch (10 queries)**: 5-10 minutes

### System Capacity
- **Concurrent users**: 50-100
- **Documents**: 1000+ PDFs
- **Monthly queries**: 10,000+

## 💰 Cost Estimation

### AWS Monthly Costs
- EC2 t3.medium: ~$30
- RDS db.t3.micro: ~$20
- S3 storage: ~$1-5
- Data transfer: ~$1-2
- **Total**: ~$50-60/month

### Groq API Costs
- Free tier: 30 requests/minute
- Paid: Based on usage
- [Pricing details](https://console.groq.com)

## 📚 Documentation

- [AWS Deployment Guide](./AWS_DEPLOYMENT_GUIDE.md) - Complete AWS setup
- [Quick Start Guide](./QUICKSTART.md) - 5-minute reference
- [API Reference](./docs/API_REFERENCE.md) - Endpoint documentation
- [Architecture Overview](./docs/ARCHITECTURE.md) - System design

## 🐛 Troubleshooting

### Common Issues

#### AWS Credentials Not Working
```bash
aws sts get-caller-identity  # Test connection
aws configure                 # Reconfigure credentials
```

#### Groq API Rate Limits
- Add delays between requests
- Use batch processing
- Monitor API usage in console

#### Database Connection Timeout
- Wait 5-10 minutes for RDS initialization
- Check security group rules
- Verify connection string

#### EC2 Instance Not Responding
- Check EC2 console for errors
- Review CloudWatch logs
- Verify instance has internet access

See [AWS_DEPLOYMENT_GUIDE.md](./AWS_DEPLOYMENT_GUIDE.md#troubleshooting) for more solutions.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

## 🙋 Support

For help:
1. Check [QUICKSTART.md](./QUICKSTART.md)
2. Review [AWS_DEPLOYMENT_GUIDE.md](./AWS_DEPLOYMENT_GUIDE.md)
3. Run `python manage_app.py status` to diagnose issues
4. Check application logs in CloudWatch

## 🔗 Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [AWS Documentation](https://docs.aws.amazon.com/)
- [Groq API Docs](https://console.groq.com/docs)
- [LangChain Documentation](https://python.langchain.com/)

## 📝 Changelog

### v1.0 (Current)
- ✅ Complete AWS deployment system
- ✅ Groq multi-agent consensus
- ✅ Django REST API
- ✅ Docker support
- ✅ Comprehensive testing
- ✅ Production-ready security

---

**Status**: ✅ Production Ready  
**Version**: 1.0  
**Last Updated**: 2024

**Made with ❤️ for medical intelligence**
