"""
Complete AWS Deployment System with Groq Consensus Integration
Deploys Django medical summary app to AWS with RDS, EC2, and S3 support
"""

import os
import sys
import json
import boto3
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


class AWSDeploymentManager:
    """Manages AWS deployment for the medical summary application"""
    
    def __init__(self, config: Optional[Dict[str, str]] = None):
        """Initialize AWS deployment manager with configuration"""
        
        self.aws_config = {
            'region': os.getenv('AWS_REGION', 'us-east-1'),
            'access_key': os.getenv('AWS_ACCESS_KEY_ID'),
            'secret_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
            'bucket_name': os.getenv('S3_BUCKET_NAME', 'medical-app-bucket'),
            'instance_type': os.getenv('EC2_INSTANCE_TYPE', 't3.medium'),
            'db_name': os.getenv('RDS_DB_NAME', 'medicalapp'),
            'db_user': os.getenv('RDS_DB_USER', 'admin'),
            'db_password': os.getenv('RDS_DB_PASSWORD', 'ChangeMe123!'),
            'db_instance_class': os.getenv('DB_INSTANCE_CLASS', 'db.t3.micro'),
        }
        
        # Override with provided config
        if config:
            self.aws_config.update(config)
        
        # Initialize AWS clients
        self.s3_client = boto3.client(
            's3',
            region_name=self.aws_config['region'],
            aws_access_key_id=self.aws_config['access_key'],
            aws_secret_access_key=self.aws_config['secret_key']
        )
        
        self.ec2_client = boto3.client(
            'ec2',
            region_name=self.aws_config['region'],
            aws_access_key_id=self.aws_config['access_key'],
            aws_secret_access_key=self.aws_config['secret_key']
        )
        
        self.rds_client = boto3.client(
            'rds',
            region_name=self.aws_config['region'],
            aws_access_key_id=self.aws_config['access_key'],
            aws_secret_access_key=self.aws_config['secret_key']
        )
        
        self.iam_client = boto3.client(
            'iam',
            aws_access_key_id=self.aws_config['access_key'],
            aws_secret_access_key=self.aws_config['secret_key']
        )
        
        logger.info(f"AWS Deployment Manager initialized for region: {self.aws_config['region']}")
    
    # ============================================================================
    # S3 BUCKET MANAGEMENT
    # ============================================================================
    
    def create_s3_bucket(self, bucket_name: Optional[str] = None) -> bool:
        """Create S3 bucket for application storage"""
        
        bucket_name = bucket_name or self.aws_config['bucket_name']
        
        try:
            logger.info(f"Creating S3 bucket: {bucket_name}")
            
            # Check if bucket already exists
            response = self.s3_client.list_buckets()
            existing_buckets = [b['Name'] for b in response['Buckets']]
            
            if bucket_name in existing_buckets:
                logger.info(f"Bucket {bucket_name} already exists")
                return True
            
            # Create bucket
            if self.aws_config['region'] == 'us-east-1':
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.aws_config['region']}
                )
            
            # Enable versioning
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            
            # Block public access
            self.s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )
            
            logger.info(f"S3 bucket created successfully: {bucket_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating S3 bucket: {e}")
            return False
    
    def upload_application_to_s3(self, local_path: str = "./server", 
                                exclude_patterns: List[str] = None) -> bool:
        """Upload application files to S3"""
        
        if exclude_patterns is None:
            exclude_patterns = ['*.pyc', '__pycache__', '.git', 'node_modules', '.env', 'db.sqlite3']
        
        try:
            logger.info(f"Uploading application from {local_path} to S3")
            
            uploaded_count = 0
            for root, dirs, files in os.walk(local_path):
                # Remove excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_patterns]
                
                for file in files:
                    # Skip excluded files
                    if any(file.endswith(pattern.replace('*', '')) for pattern in exclude_patterns):
                        continue
                    
                    file_path = os.path.join(root, file)
                    s3_key = os.path.relpath(file_path, local_path)
                    
                    try:
                        self.s3_client.upload_file(
                            file_path,
                            self.aws_config['bucket_name'],
                            s3_key
                        )
                        uploaded_count += 1
                        logger.debug(f"Uploaded: {s3_key}")
                    except Exception as e:
                        logger.warning(f"Failed to upload {file_path}: {e}")
            
            logger.info(f"Successfully uploaded {uploaded_count} files to S3")
            return True
        
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            return False
    
    def create_s3_folders(self) -> bool:
        """Create folder structure in S3"""
        
        try:
            folders = [
                'insurance_docs/',
                'uploads/',
                'exports/',
                'logs/',
                'backups/',
                'consensus_results/'
            ]
            
            for folder in folders:
                self.s3_client.put_object(
                    Bucket=self.aws_config['bucket_name'],
                    Key=folder
                )
                logger.info(f"Created S3 folder: {folder}")
            
            return True
        except Exception as e:
            logger.error(f"Error creating S3 folders: {e}")
            return False
    
    # ============================================================================
    # RDS DATABASE MANAGEMENT
    # ============================================================================
    
    def create_rds_database(self) -> Dict[str, Any]:
        """Create RDS PostgreSQL database"""
        
        try:
            logger.info("Creating RDS PostgreSQL database...")
            
            db_instance_identifier = 'medical-app-db'
            
            # Check if instance already exists
            try:
                response = self.rds_client.describe_db_instances(
                    DBInstanceIdentifier=db_instance_identifier
                )
                logger.info(f"Database instance {db_instance_identifier} already exists")
                return {
                    'endpoint': response['DBInstances'][0]['Endpoint']['Address'],
                    'port': response['DBInstances'][0]['Endpoint']['Port']
                }
            except self.rds_client.exceptions.DBInstanceNotFoundFault:
                pass
            
            # Create security group first
            security_group_id = self._create_security_group()
            
            # Create RDS instance
            response = self.rds_client.create_db_instance(
                DBInstanceIdentifier=db_instance_identifier,
                DBInstanceClass=self.aws_config['db_instance_class'],
                Engine='postgres',
                EngineVersion='15.4',
                MasterUsername=self.aws_config['db_user'],
                MasterUserPassword=self.aws_config['db_password'],
                AllocatedStorage=100,
                StorageType='gp3',
                StorageEncrypted=True,
                DBName=self.aws_config['db_name'],
                VpcSecurityGroupIds=[security_group_id],
                BackupRetentionPeriod=30,
                PreferredBackupWindow='03:00-04:00',
                PreferredMaintenanceWindow='sun:04:00-sun:05:00',
                EnableCloudwatchLogsExports=['postgresql'],
                EnableIAMDatabaseAuthentication=True,
                MultiAZ=True,
                Tags=[
                    {'Key': 'Application', 'Value': 'MedicalSummaryApp'},
                    {'Key': 'Environment', 'Value': 'Production'}
                ]
            )
            
            endpoint = response['DBInstance']['Endpoint']['Address']
            port = response['DBInstance']['Endpoint']['Port']
            
            logger.info(f"RDS database created: {db_instance_identifier}")
            logger.info(f"Endpoint: {endpoint}:{port}")
            logger.info("Note: Database may take 5-10 minutes to become available")
            
            return {
                'endpoint': endpoint,
                'port': port,
                'instance_id': db_instance_identifier
            }
        
        except Exception as e:
            logger.error(f"Error creating RDS database: {e}")
            return {}
    
    def _create_security_group(self) -> str:
        """Create VPC security group for RDS"""
        
        try:
            # Get default VPC
            vpcs = self.ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
            vpc_id = vpcs['Vpcs'][0]['VpcId']
            
            sg_name = 'medical-app-rds-sg'
            
            # Check if security group exists
            try:
                response = self.ec2_client.describe_security_groups(
                    Filters=[{'Name': 'group-name', 'Values': [sg_name]}]
                )
                if response['SecurityGroups']:
                    logger.info(f"Security group {sg_name} already exists")
                    return response['SecurityGroups'][0]['GroupId']
            except:
                pass
            
            # Create security group
            response = self.ec2_client.create_security_group(
                GroupName=sg_name,
                Description='Security group for medical app RDS',
                VpcId=vpc_id
            )
            
            sg_id = response['GroupId']
            
            # Add ingress rule for PostgreSQL
            self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 5432,
                        'ToPort': 5432,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'PostgreSQL access'}]
                    }
                ]
            )
            
            logger.info(f"Security group created: {sg_id}")
            return sg_id
        
        except Exception as e:
            logger.error(f"Error creating security group: {e}")
            return ""
    
    # ============================================================================
    # EC2 INSTANCE MANAGEMENT
    # ============================================================================
    
    def create_ec2_instance(self) -> Dict[str, str]:
        """Create EC2 instance for application"""
        
        try:
            logger.info("Creating EC2 instance...")
            
            # Get latest Ubuntu 22.04 LTS AMI
            ami_id = self._get_ubuntu_ami()
            
            if not ami_id:
                logger.error("Could not find Ubuntu AMI")
                return {}
            
            # Create security group for EC2
            sg_id = self._create_ec2_security_group()
            
            # Create instance
            instances = self.ec2_client.run_instances(
                ImageId=ami_id,
                MinCount=1,
                MaxCount=1,
                InstanceType=self.aws_config['instance_type'],
                SecurityGroupIds=[sg_id],
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': 'medical-app-server'},
                            {'Key': 'Application', 'Value': 'MedicalSummaryApp'}
                        ]
                    }
                ],
                UserData=self._get_ec2_userdata()
            )
            
            instance_id = instances['Instances'][0]['InstanceId']
            logger.info(f"EC2 instance created: {instance_id}")
            
            # Wait for instance to be running
            waiter = self.ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=[instance_id])
            
            # Get instance details
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            
            public_ip = instance.get('PublicIpAddress', 'N/A')
            
            logger.info(f"EC2 instance is running")
            logger.info(f"Public IP: {public_ip}")
            
            return {
                'instance_id': instance_id,
                'public_ip': public_ip,
                'security_group': sg_id
            }
        
        except Exception as e:
            logger.error(f"Error creating EC2 instance: {e}")
            return {}
    
    def _get_ubuntu_ami(self) -> Optional[str]:
        """Get the latest Ubuntu 22.04 LTS AMI"""
        
        try:
            response = self.ec2_client.describe_images(
                Owners=['099720109477'],  # Canonical
                Filters=[
                    {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']},
                    {'Name': 'state', 'Values': ['available']}
                ]
            )
            
            if response['Images']:
                return sorted(response['Images'], 
                            key=lambda x: x['CreationDate'], 
                            reverse=True)[0]['ImageId']
            return None
        except Exception as e:
            logger.error(f"Error getting Ubuntu AMI: {e}")
            return None
    
    def _create_ec2_security_group(self) -> str:
        """Create security group for EC2"""
        
        try:
            vpcs = self.ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
            vpc_id = vpcs['Vpcs'][0]['VpcId']
            
            sg_name = 'medical-app-ec2-sg'
            
            try:
                response = self.ec2_client.describe_security_groups(
                    Filters=[{'Name': 'group-name', 'Values': [sg_name]}]
                )
                if response['SecurityGroups']:
                    return response['SecurityGroups'][0]['GroupId']
            except:
                pass
            
            response = self.ec2_client.create_security_group(
                GroupName=sg_name,
                Description='Security group for medical app EC2',
                VpcId=vpc_id
            )
            
            sg_id = response['GroupId']
            
            # Add ingress rules
            self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'SSH access'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 80,
                        'ToPort': 80,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP access'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 443,
                        'ToPort': 443,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTPS access'}]
                    }
                ]
            )
            
            logger.info(f"EC2 Security group created: {sg_id}")
            return sg_id
        
        except Exception as e:
            logger.error(f"Error creating EC2 security group: {e}")
            return ""
    
    def _get_ec2_userdata(self) -> str:
        """Generate EC2 user data script for application setup"""
        
        return """#!/bin/bash
set -e

# Update system
apt-get update
apt-get upgrade -y

# Install dependencies
apt-get install -y python3 python3-pip python3-venv git curl wget
apt-get install -y postgresql-client libpq-dev
apt-get install -y supervisor nginx

# Create application directory
mkdir -p /opt/medical-app
cd /opt/medical-app

# Clone repository or download from S3
# aws s3 cp s3://medical-app-bucket . --recursive

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files (if using Django)
# python manage.py collectstatic --noinput

# Setup environment variables
cat > /opt/medical-app/.env << EOF
DEBUG=False
ALLOWED_HOSTS=*
DATABASE_URL=postgresql://admin:ChangeMe123!@medical-app-db.c7x8z9y9x9x9.us-east-1.rds.amazonaws.com:5432/medicalapp
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
S3_BUCKET_NAME=medical-app-bucket
GROQ_API_KEY=${GROQ_API_KEY}
EOF

# Setup Nginx
cp nginx.conf /etc/nginx/sites-available/medical-app
ln -s /etc/nginx/sites-available/medical-app /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# Setup Supervisor for Gunicorn
cat > /etc/supervisor/conf.d/medical-app.conf << 'SUPERVISOR_EOF'
[program:medical-app]
directory=/opt/medical-app
command=/opt/medical-app/venv/bin/gunicorn core.wsgi:application --bind 127.0.0.1:8000 --workers 4
autostart=true
autorestart=true
stderr_logfile=/var/log/medical-app.err.log
stdout_logfile=/var/log/medical-app.out.log
SUPERVISOR_EOF

supervisorctl reread
supervisorctl update

# Setup log rotation
cat > /etc/logrotate.d/medical-app << 'LOGROTATE_EOF'
/var/log/medical-app.*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        supervisorctl restart medical-app > /dev/null
    endscript
}
LOGROTATE_EOF

echo "EC2 instance setup completed"
"""
    
    # ============================================================================
    # DEPLOYMENT ORCHESTRATION
    # ============================================================================
    
    def full_deployment(self, db_config: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute full application deployment"""
        
        logger.info("=" * 80)
        logger.info("STARTING FULL AWS DEPLOYMENT")
        logger.info("=" * 80)
        
        deployment_result = {
            'timestamp': datetime.now().isoformat(),
            's3': {},
            'rds': {},
            'ec2': {},
            'success': True
        }
        
        try:
            # Step 1: S3 Setup
            logger.info("\n[Step 1/4] Setting up S3...")
            if self.create_s3_bucket():
                if self.create_s3_folders():
                    if self.upload_application_to_s3():
                        deployment_result['s3']['status'] = 'success'
                        logger.info("✓ S3 setup completed")
                    else:
                        deployment_result['s3']['status'] = 'warning'
                        logger.warning("! S3 upload had issues")
            
            # Step 2: RDS Setup
            logger.info("\n[Step 2/4] Setting up RDS Database...")
            rds_info = self.create_rds_database()
            if rds_info:
                deployment_result['rds'] = rds_info
                logger.info("✓ RDS setup completed")
            else:
                deployment_result['success'] = False
                logger.error("✗ RDS setup failed")
            
            # Step 3: EC2 Setup
            logger.info("\n[Step 3/4] Setting up EC2 Instance...")
            ec2_info = self.create_ec2_instance()
            if ec2_info:
                deployment_result['ec2'] = ec2_info
                logger.info("✓ EC2 setup completed")
            else:
                deployment_result['success'] = False
                logger.error("✗ EC2 setup failed")
            
            # Step 4: Generate deployment configuration
            logger.info("\n[Step 4/4] Generating deployment configuration...")
            config = self._generate_deployment_config(deployment_result)
            deployment_result['config'] = config
            logger.info("✓ Configuration generated")
            
            # Save deployment report
            self._save_deployment_report(deployment_result)
            
            logger.info("\n" + "=" * 80)
            logger.info("DEPLOYMENT COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            deployment_result['success'] = False
            deployment_result['error'] = str(e)
        
        return deployment_result
    
    def _generate_deployment_config(self, deployment_result: Dict) -> str:
        """Generate deployment configuration file"""
        
        config = f"""
# Medical Summary App - AWS Deployment Configuration
# Generated: {datetime.now().isoformat()}

## Database Configuration
DATABASE_URL=postgresql://{self.aws_config['db_user']}:{self.aws_config['db_password']}@{deployment_result['rds'].get('endpoint', 'PENDING')}:5432/{self.aws_config['db_name']}

## S3 Configuration
AWS_STORAGE_BUCKET_NAME={self.aws_config['bucket_name']}
AWS_S3_REGION_NAME={self.aws_config['region']}
AWS_S3_CUSTOM_DOMAIN={self.aws_config['bucket_name']}.s3.amazonaws.com

## EC2 Configuration
EC2_INSTANCE_ID={deployment_result['ec2'].get('instance_id', 'N/A')}
EC2_PUBLIC_IP={deployment_result['ec2'].get('public_ip', 'N/A')}

## Groq Configuration
GROQ_API_KEY={os.getenv('GROQ_API_KEY', 'YOUR_GROQ_API_KEY_HERE')}
GROQ_MODEL=mixtral-8x7b-32768

## Django Configuration
DEBUG=False
ALLOWED_HOSTS={deployment_result['ec2'].get('public_ip', '*')},localhost,127.0.0.1
SECRET_KEY={os.urandom(32).hex()}

## Application Settings
LOG_LEVEL=INFO
CONSENSUS_MAX_ROUNDS=5
CONSENSUS_CONFIDENCE_THRESHOLD=0.75
"""
        
        return config.strip()
    
    def _save_deployment_report(self, deployment_result: Dict):
        """Save deployment report to S3 and local file"""
        
        try:
            report = json.dumps(deployment_result, indent=2, default=str)
            
            # Save locally
            report_file = f"deployment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                f.write(report)
            logger.info(f"Deployment report saved: {report_file}")
            
            # Save to S3
            try:
                self.s3_client.put_object(
                    Bucket=self.aws_config['bucket_name'],
                    Key=f'deployments/{report_file}',
                    Body=report
                )
                logger.info(f"Deployment report uploaded to S3: deployments/{report_file}")
            except Exception as e:
                logger.warning(f"Could not upload report to S3: {e}")
        
        except Exception as e:
            logger.error(f"Error saving deployment report: {e}")


class GroqIntegration:
    """Integrates Groq consensus system with AWS deployment"""
    
    def __init__(self, deployment_manager: AWSDeploymentManager):
        self.deployment_manager = deployment_manager
        self.groq_api_key = os.getenv('GROQ_API_KEY')
    
    def save_consensus_result(self, consensus_result: Dict, result_name: str) -> bool:
        """Save consensus result to S3"""
        
        try:
            key = f"consensus_results/{result_name}_{datetime.now().isoformat()}.json"
            
            self.deployment_manager.s3_client.put_object(
                Bucket=self.deployment_manager.aws_config['bucket_name'],
                Key=key,
                Body=json.dumps(consensus_result, indent=2, default=str)
            )
            
            logger.info(f"Consensus result saved to S3: {key}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving consensus result: {e}")
            return False


def main():
    """Main deployment function"""
    
    # Initialize deployment manager
    deployment_manager = AWSDeploymentManager()
    
    # Run full deployment
    result = deployment_manager.full_deployment()
    
    # Print deployment summary
    print("\n" + "=" * 80)
    print("DEPLOYMENT SUMMARY")
    print("=" * 80)
    print(f"Status: {'SUCCESS' if result['success'] else 'FAILED'}")
    print(f"Timestamp: {result['timestamp']}")
    
    if result['s3']:
        print(f"\nS3 Bucket: {deployment_manager.aws_config['bucket_name']}")
        print(f"  Status: {result['s3'].get('status', 'N/A')}")
    
    if result['rds']:
        print(f"\nRDS Database: {result['rds'].get('instance_id', 'N/A')}")
        print(f"  Endpoint: {result['rds'].get('endpoint', 'N/A')}")
        print(f"  Port: {result['rds'].get('port', 'N/A')}")
    
    if result['ec2']:
        print(f"\nEC2 Instance: {result['ec2'].get('instance_id', 'N/A')}")
        print(f"  Public IP: {result['ec2'].get('public_ip', 'N/A')}")
    
    if 'config' in result:
        print(f"\nDeployment Configuration:")
        print(result['config'])
    
    print("\n" + "=" * 80)
    
    return result


if __name__ == "__main__":
    main()