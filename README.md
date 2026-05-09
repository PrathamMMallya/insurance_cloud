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

# Wait 5-10 minutes for resources to initialize
# Note: RDS takes 5-10 minutes to become available
```

### Step 4: Access Application
```
http://your-ec2-public-ip
```


## 🔌 API Usage

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

