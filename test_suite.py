"""
Comprehensive Testing Suite for Groq Consensus System and AWS Deployment
"""

import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq_consensus import (
    GroqConsensusAgent, 
    GroqConsensusSystem, 
    AgentRole,
    ConsensusResult
)


class TestGroqConsensusAgent(unittest.TestCase):
    """Test individual consensus agents"""
    
    def setUp(self):
        """Set up test fixtures"""
        os.environ['GROQ_API_KEY'] = 'test-key'
    
    def test_agent_initialization(self):
        """Test agent can be initialized with different roles"""
        for role in AgentRole:
            agent = GroqConsensusAgent(
                agent_id=f"test-agent-{role.value}",
                role=role
            )
            self.assertEqual(agent.role, role)
            self.assertIsNone(agent.position)
            self.assertEqual(agent.confidence, 0.0)
    
    @patch('groq_consensus.Groq')
    def test_agent_analysis(self, mock_groq):
        """Test agent analysis process"""
        # Mock Groq API response
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Test analysis result")]
        mock_client.messages.create.return_value = mock_message
        mock_groq.return_value = mock_client
        
        agent = GroqConsensusAgent("test-agent", AgentRole.ANALYZER)
        result = agent.analyze("Test context", "Test query")
        
        self.assertIsNotNone(result)
        self.assertEqual(agent.position, "Test analysis result")


class TestGroqConsensusSystem(unittest.TestCase):
    """Test consensus system"""
    
    def setUp(self):
        """Set up test fixtures"""
        os.environ['GROQ_API_KEY'] = 'test-key'
    
    def test_system_initialization(self):
        """Test system initialization"""
        system = GroqConsensusSystem(num_agents=4, max_rounds=5)
        self.assertEqual(len(system.agents), 4)
        self.assertEqual(system.max_rounds, 5)
    
    def test_agent_roles(self):
        """Test all agent roles are created"""
        system = GroqConsensusSystem(num_agents=4)
        roles = [agent.role for agent in system.agents]
        
        self.assertIn(AgentRole.ANALYZER, roles)
        self.assertIn(AgentRole.VALIDATOR, roles)
        self.assertIn(AgentRole.CRITIC, roles)
        self.assertIn(AgentRole.SYNTHESIZER, roles)
    
    @patch('groq_consensus.Groq')
    def test_consensus_result_structure(self, mock_groq):
        """Test consensus result has correct structure"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Test response")]
        mock_client.messages.create.return_value = mock_message
        mock_groq.return_value = mock_client
        
        system = GroqConsensusSystem(num_agents=2, max_rounds=2)
        result = system.reach_consensus("Test context", "Test query")
        
        self.assertIsInstance(result, ConsensusResult)
        self.assertIsNotNone(result.final_decision)
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)
        self.assertGreaterEqual(result.negotiation_rounds, 1)
        self.assertIsNotNone(result.timestamp)


class TestAWSDeployment(unittest.TestCase):
    """Test AWS deployment functionality"""
    
    @patch('deploy_to_aws.boto3.client')
    def test_deployment_manager_initialization(self, mock_boto3_client):
        """Test deployment manager initializes with AWS clients"""
        from deploy_to_aws import AWSDeploymentManager
        
        manager = AWSDeploymentManager()
        
        self.assertIsNotNone(manager.s3_client)
        self.assertIsNotNone(manager.ec2_client)
        self.assertIsNotNone(manager.rds_client)
        self.assertIsNotNone(manager.iam_client)
    
    @patch('deploy_to_aws.boto3.client')
    def test_aws_config(self, mock_boto3_client):
        """Test AWS configuration is set correctly"""
        from deploy_to_aws import AWSDeploymentManager
        
        os.environ['AWS_REGION'] = 'us-west-2'
        os.environ['S3_BUCKET_NAME'] = 'test-bucket'
        
        manager = AWSDeploymentManager()
        
        self.assertEqual(manager.aws_config['region'], 'us-west-2')
        self.assertEqual(manager.aws_config['bucket_name'], 'test-bucket')


class TestConsensusIntegration(unittest.TestCase):
    """Test consensus system integration scenarios"""
    
    @patch('groq_consensus.Groq')
    def test_medical_document_consensus(self, mock_groq):
        """Test consensus on medical document analysis"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Patient should be covered under the policy")]
        mock_client.messages.create.return_value = mock_message
        mock_groq.return_value = mock_client
        
        system = GroqConsensusSystem(num_agents=2, max_rounds=2)
        
        context = """
        Health Insurance Policy:
        - Coverage: Hospitalization, Surgery, Medication
        - Age Limit: 18-65
        - Deductible: $1000
        """
        
        query = "Should a 45-year-old with controlled diabetes be covered?"
        result = system.reach_consensus(context, query)
        
        self.assertIsNotNone(result)
        self.assertGreater(len(result.agent_positions), 0)
    
    @patch('groq_consensus.Groq')
    def test_consensus_json_conversion(self, mock_groq):
        """Test consensus result conversion to JSON"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Test decision")]
        mock_client.messages.create.return_value = mock_message
        mock_groq.return_value = mock_client
        
        system = GroqConsensusSystem(num_agents=2, max_rounds=2)
        result = system.reach_consensus("Context", "Query")
        
        json_str = system.get_consensus_json(result)
        parsed = json.loads(json_str)
        
        self.assertIn('final_decision', parsed)
        self.assertIn('confidence_score', parsed)
        self.assertIn('negotiation_rounds', parsed)
        self.assertIn('timestamp', parsed)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""
    
    @patch('groq_consensus.Groq')
    def test_empty_context(self, mock_groq):
        """Test handling of empty context"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Response")]
        mock_client.messages.create.return_value = mock_message
        mock_groq.return_value = mock_client
        
        system = GroqConsensusSystem(num_agents=1, max_rounds=1)
        # Should handle empty context gracefully
        result = system.reach_consensus("", "Query")
        
        self.assertIsNotNone(result)
    
    @patch('groq_consensus.Groq')
    def test_groq_api_error(self, mock_groq):
        """Test handling of Groq API errors"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_groq.return_value = mock_client
        
        agent = GroqConsensusAgent("test", AgentRole.ANALYZER)
        result = agent.analyze("Context", "Query")
        
        self.assertIn("Error", result)


class TestPerformance(unittest.TestCase):
    """Test performance metrics"""
    
    @patch('groq_consensus.Groq')
    def test_consensus_timing(self, mock_groq):
        """Test consensus execution time"""
        import time
        
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Response")]
        mock_client.messages.create.return_value = mock_message
        mock_groq.return_value = mock_client
        
        system = GroqConsensusSystem(num_agents=2, max_rounds=2)
        
        start_time = time.time()
        result = system.reach_consensus("Context", "Query")
        elapsed = time.time() - start_time
        
        # Should complete in reasonable time (even with mocks)
        self.assertLess(elapsed, 30)
        self.assertGreater(result.negotiation_rounds, 0)


# Test Suite
def run_all_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestGroqConsensusAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestGroqConsensusSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestAWSDeployment))
    suite.addTests(loader.loadTestsFromTestCase(TestConsensusIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
