#!/usr/bin/env python
"""
Medical Summary App - Management Utility Script
Handles deployment, configuration, and operational tasks
"""

import argparse
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MedicalAppManager:
    """Management utility for medical summary application"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.env_file = self.project_root / '.env'
        self.requirements_file = self.project_root / 'requirements.txt'
    
    # ============================================================================
    # SETUP COMMANDS
    # ============================================================================
    
    def setup_environment(self):
        """Initialize local development environment"""
        logger.info("Setting up local environment...")
        
        try:
            # Create virtual environment
            logger.info("Creating virtual environment...")
            subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
            
            # Install requirements
            logger.info("Installing requirements...")
            venv_python = 'venv\\Scripts\\python' if os.name == 'nt' else 'venv/bin/python'
            subprocess.run([venv_python, '-m', 'pip', 'install', '-r', str(self.requirements_file)], check=True)
            
            # Copy environment template
            if not self.env_file.exists():
                logger.info("Creating .env from .env.example...")
                env_example = self.project_root / '.env.example'
                if env_example.exists():
                    with open(env_example) as src, open(self.env_file, 'w') as dst:
                        dst.write(src.read())
                    logger.warning("⚠ Please configure .env with your credentials")
            
            logger.info("✓ Environment setup complete")
            logger.info("✓ Run: source venv/Scripts/activate (Windows) or source venv/bin/activate (Linux/Mac)")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Setup failed: {e}")
            return False
        
        return True
    
    def setup_django(self):
        """Initialize Django database and static files"""
        logger.info("Setting up Django...")
        
        try:
            # Run migrations
            logger.info("Running migrations...")
            subprocess.run([sys.executable, 'server/manage.py', 'migrate'], check=True)
            
            # Collect static files
            logger.info("Collecting static files...")
            subprocess.run([sys.executable, 'server/manage.py', 'collectstatic', '--noinput'], check=True)
            
            logger.info("✓ Django setup complete")
            logger.info("✓ Create superuser: python server/manage.py createsuperuser")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Django setup failed: {e}")
            return False
        
        return True
    
    # ============================================================================
    # DEPLOYMENT COMMANDS
    # ============================================================================
    
    def deploy_aws(self, dry_run: bool = False):
        """Deploy application to AWS"""
        
        if dry_run:
            logger.info("DRY RUN: Checking deployment configuration...")
        else:
            logger.info("Starting AWS deployment...")
        
        try:
            if not self.env_file.exists():
                logger.error("ERROR: .env file not found. Run 'setup' first.")
                return False
            
            # Verify AWS credentials
            logger.info("Verifying AWS credentials...")
            try:
                subprocess.run(['aws', 'sts', 'get-caller-identity'], 
                             capture_output=True, check=True)
                logger.info("✓ AWS credentials verified")
            except subprocess.CalledProcessError:
                logger.error("ERROR: AWS credentials not configured. Run 'aws configure'")
                return False
            
            # Run deployment
            if not dry_run:
                logger.info("Deploying to AWS...")
                subprocess.run([sys.executable, 'deploy_to_aws.py'], check=True)
            
            logger.info("✓ Deployment configuration validated")
            logger.info("Next: Check deployment_report_*.json for results")
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False
        
        return True
    
    def deploy_docker(self):
        """Deploy using Docker Compose"""
        logger.info("Deploying with Docker Compose...")
        
        try:
            logger.info("Building Docker images...")
            subprocess.run(['docker-compose', 'build'], check=True)
            
            logger.info("Starting services...")
            subprocess.run(['docker-compose', 'up', '-d'], check=True)
            
            logger.info("Running migrations...")
            subprocess.run(['docker-compose', 'exec', 'app', 'python', 'manage.py', 'migrate'], check=True)
            
            logger.info("✓ Docker deployment complete")
            logger.info("✓ Access at http://localhost")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker deployment failed: {e}")
            return False
        
        return True
    
    # ============================================================================
    # TESTING COMMANDS
    # ============================================================================
    
    def run_tests(self, test_type: str = 'all'):
        """Run application tests"""
        logger.info(f"Running {test_type} tests...")
        
        try:
            if test_type in ['all', 'consensus']:
                logger.info("Testing Groq Consensus System...")
                subprocess.run([sys.executable, 'test_suite.py'], check=True)
            
            if test_type in ['all', 'django']:
                logger.info("Running Django tests...")
                subprocess.run([sys.executable, 'server/manage.py', 'test'], check=True)
            
            logger.info("✓ Tests passed")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Tests failed: {e}")
            return False
        
        return True
    
    def test_groq_connection(self):
        """Test Groq API connection"""
        logger.info("Testing Groq API connection...")
        
        try:
            from groq import Groq
            api_key = os.getenv('GROQ_API_KEY')
            
            if not api_key:
                logger.error("ERROR: GROQ_API_KEY not set in .env")
                return False
            
            client = Groq(api_key=api_key)
            message = client.messages.create(
                model="mixtral-8x7b-32768",
                max_tokens=100,
                messages=[{"role": "user", "content": "Say 'Connection successful' if you can see this."}]
            )
            
            logger.info(f"✓ Groq API connected: {message.content[0].text}")
            return True
            
        except Exception as e:
            logger.error(f"Groq API connection failed: {e}")
            return False
    
    def test_aws_connection(self):
        """Test AWS connection"""
        logger.info("Testing AWS connection...")
        
        try:
            import boto3
            
            # Test S3
            s3 = boto3.client('s3')
            buckets = s3.list_buckets()
            logger.info(f"✓ S3 connected: {len(buckets['Buckets'])} buckets found")
            
            # Test EC2
            ec2 = boto3.client('ec2')
            instances = ec2.describe_instances()
            total = sum(len(r['Instances']) for r in instances['Reservations'])
            logger.info(f"✓ EC2 connected: {total} instances found")
            
            return True
            
        except Exception as e:
            logger.error(f"AWS connection failed: {e}")
            return False
    
    # ============================================================================
    # UTILITY COMMANDS
    # ============================================================================
    
    def show_status(self):
        """Display system status"""
        logger.info("Checking system status...")
        
        print("\n" + "="*70)
        print("SYSTEM STATUS")
        print("="*70)
        
        # Python version
        print(f"Python Version: {sys.version.split()[0]}")
        
        # Virtual environment
        in_venv = sys.prefix != sys.base_prefix
        print(f"Virtual Environment: {'✓ Active' if in_venv else '✗ Not active'}")
        
        # Environment variables
        print(f".env File: {'✓ Found' if self.env_file.exists() else '✗ Not found'}")
        
        # AWS
        try:
            result = subprocess.run(['aws', 'sts', 'get-caller-identity'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("AWS Credentials: ✓ Configured")
            else:
                print("AWS Credentials: ✗ Not configured")
        except:
            print("AWS Credentials: ✗ Not available")
        
        # Groq API
        if os.getenv('GROQ_API_KEY'):
            print("Groq API Key: ✓ Set")
        else:
            print("Groq API Key: ✗ Not set")
        
        # Docker
        try:
            subprocess.run(['docker', '--version'], capture_output=True, check=True)
            print("Docker: ✓ Installed")
        except:
            print("Docker: ✗ Not installed")
        
        print("="*70 + "\n")
    
    def generate_config(self):
        """Generate deployment configuration template"""
        logger.info("Generating configuration template...")
        
        config = {
            'application': {
                'name': 'Medical Summary App',
                'version': '1.0',
                'created': datetime.now().isoformat()
            },
            'aws': {
                'region': os.getenv('AWS_REGION', 'us-east-1'),
                's3_bucket': os.getenv('S3_BUCKET_NAME', 'medical-app-bucket'),
                'rds_instance': 'medical-app-db',
                'ec2_instance_type': os.getenv('EC2_INSTANCE_TYPE', 't3.medium')
            },
            'api': {
                'groq_model': 'mixtral-8x7b-32768',
                'consensus_agents': 4,
                'max_rounds': 5,
                'confidence_threshold': 0.75
            },
            'features': {
                'document_upload': True,
                'consensus_processing': True,
                'aws_integration': True,
                'docker_support': True
            }
        }
        
        config_file = self.project_root / 'deployment_config.json'
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"✓ Configuration saved to {config_file}")
    
    def cleanup(self, target: str = 'all'):
        """Clean up temporary files and resources"""
        logger.info(f"Cleaning up {target} resources...")
        
        patterns = {
            'pyc': ['**/*.pyc', '**/__pycache__'],
            'logs': ['**/*.log', 'logs/'],
            'cache': ['.pytest_cache', '.mypy_cache'],
            'temp': ['*.tmp', 'temp/', 'tmp/']
        }
        
        targets = patterns.keys() if target == 'all' else [target]
        
        for t in targets:
            if t in patterns:
                for pattern in patterns[t]:
                    for item in self.project_root.glob(pattern):
                        if item.is_file():
                            item.unlink()
                            logger.info(f"Deleted: {item}")
                        elif item.is_dir():
                            import shutil
                            shutil.rmtree(item)
                            logger.info(f"Deleted directory: {item}")
        
        logger.info("✓ Cleanup complete")


def main():
    """Main CLI entry point"""
    
    parser = argparse.ArgumentParser(
        description='Medical Summary App - Management Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage_app.py setup              # Initialize environment
  python manage_app.py deploy-aws         # Deploy to AWS
  python manage_app.py deploy-docker      # Deploy with Docker
  python manage_app.py test --type=all    # Run all tests
  python manage_app.py status             # Show system status
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Setup command
    subparsers.add_parser('setup', help='Initialize local development environment')
    subparsers.add_parser('setup-django', help='Initialize Django database')
    
    # Deployment commands
    deploy_aws_parser = subparsers.add_parser('deploy-aws', help='Deploy to AWS')
    deploy_aws_parser.add_argument('--dry-run', action='store_true', help='Dry run without deploying')
    
    subparsers.add_parser('deploy-docker', help='Deploy with Docker Compose')
    
    # Testing commands
    test_parser = subparsers.add_parser('test', help='Run tests')
    test_parser.add_argument('--type', choices=['all', 'consensus', 'django'], 
                            default='all', help='Test type to run')
    
    subparsers.add_parser('test-groq', help='Test Groq API connection')
    subparsers.add_parser('test-aws', help='Test AWS connection')
    
    # Utility commands
    subparsers.add_parser('status', help='Show system status')
    subparsers.add_parser('config', help='Generate deployment configuration')
    
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up temporary files')
    cleanup_parser.add_argument('--target', choices=['all', 'pyc', 'logs', 'cache', 'temp'],
                               default='all', help='What to clean')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute command
    manager = MedicalAppManager()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'setup':
            success = manager.setup_environment()
        elif args.command == 'setup-django':
            success = manager.setup_django()
        elif args.command == 'deploy-aws':
            success = manager.deploy_aws(dry_run=args.dry_run)
        elif args.command == 'deploy-docker':
            success = manager.deploy_docker()
        elif args.command == 'test':
            success = manager.run_tests(test_type=args.type)
        elif args.command == 'test-groq':
            success = manager.test_groq_connection()
        elif args.command == 'test-aws':
            success = manager.test_aws_connection()
        elif args.command == 'status':
            manager.show_status()
            success = True
        elif args.command == 'config':
            manager.generate_config()
            success = True
        elif args.command == 'cleanup':
            manager.cleanup(target=args.target)
            success = True
        else:
            logger.error(f"Unknown command: {args.command}")
            success = False
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
