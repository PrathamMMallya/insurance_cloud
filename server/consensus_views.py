"""
Django Integration with Groq Consensus System
Handles consensus-based medical document analysis and insurance decisions
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq_consensus import GroqConsensusSystem, ConsensusResult
from deploy_to_aws import GroqIntegration, AWSDeploymentManager

logger = logging.getLogger(__name__)


class GroqConsensusView(View):
    """Handle Groq consensus processing for insurance documents"""
    
    def __init__(self):
        super().__init__()
        self.consensus_system = GroqConsensusSystem(
            num_agents=4,
            max_rounds=int(os.getenv('CONSENSUS_MAX_ROUNDS', '5'))
        )
        
        try:
            self.deployment_manager = AWSDeploymentManager()
            self.groq_integration = GroqIntegration(self.deployment_manager)
        except Exception as e:
            logger.warning(f"AWS deployment manager not initialized: {e}")
            self.groq_integration = None
    
    def post(self, request):
        """Process document analysis with consensus"""
        
        try:
            data = request.POST
            document_context = data.get('document_context', '')
            query = data.get('query', '')
            document_id = data.get('document_id')
            
            if not document_context or not query:
                return JsonResponse({
                    'success': False,
                    'error': 'Document context and query are required'
                })
            
            logger.info(f"Starting consensus process for query: {query}")
            
            # Run consensus
            result = self.consensus_system.reach_consensus(document_context, query)
            
            # Format response
            response_data = {
                'success': True,
                'final_decision': result.final_decision,
                'confidence_score': round(result.confidence_score, 3),
                'negotiation_rounds': result.negotiation_rounds,
                'timestamp': result.timestamp.isoformat(),
                'reasoning': result.reasoning,
                'agent_positions': result.agent_positions
            }
            
            # Save to AWS if configured
            if self.groq_integration:
                try:
                    self.groq_integration.save_consensus_result(
                        response_data,
                        f"document_{document_id}" if document_id else "consensus"
                    )
                except Exception as e:
                    logger.warning(f"Could not save consensus result to AWS: {e}")
            
            return JsonResponse(response_data)
        
        except Exception as e:
            logger.error(f"Error in consensus processing: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@csrf_exempt
def quick_consensus_query(request):
    """Quick endpoint for consensus queries without document"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'})
    
    try:
        query = request.POST.get('query', '')
        context = request.POST.get('context', '')
        
        if not query:
            return JsonResponse({'error': 'Query required'})
        
        consensus_system = GroqConsensusSystem(num_agents=4, max_rounds=5)
        result = consensus_system.reach_consensus(context, query)
        
        return JsonResponse({
            'success': True,
            'final_decision': result.final_decision,
            'confidence_score': round(result.confidence_score, 3),
            'rounds': result.negotiation_rounds
        })
    
    except Exception as e:
        logger.error(f"Error in quick query: {e}")
        return JsonResponse({'error': str(e)})


def consensus_status(request):
    """Display consensus system status and statistics"""
    
    try:
        consensus_system = GroqConsensusSystem()
        
        context = {
            'agents_count': len(consensus_system.agents),
            'max_rounds': consensus_system.max_rounds,
            'consensus_history_count': len(consensus_system.consensus_history),
            'recent_results': consensus_system.consensus_history[-5:] if consensus_system.consensus_history else [],
            'system_ready': True
        }
        
        return render(request, 'consensus_status.html', context)
    
    except Exception as e:
        logger.error(f"Error getting consensus status: {e}")
        return render(request, 'consensus_status.html', {
            'error': str(e),
            'system_ready': False
        })


@csrf_exempt
def batch_consensus_process(request):
    """Process multiple queries with consensus"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'})
    
    try:
        import json
        data = json.loads(request.body)
        queries = data.get('queries', [])
        context = data.get('context', '')
        
        if not queries:
            return JsonResponse({'error': 'Queries array required'})
        
        consensus_system = GroqConsensusSystem(num_agents=4, max_rounds=5)
        results = []
        
        for query_item in queries:
            query_text = query_item if isinstance(query_item, str) else query_item.get('query', '')
            if query_text:
                result = consensus_system.reach_consensus(context, query_text)
                results.append({
                    'query': query_text,
                    'decision': result.final_decision,
                    'confidence': round(result.confidence_score, 3),
                    'rounds': result.negotiation_rounds
                })
        
        return JsonResponse({
            'success': True,
            'total_queries': len(results),
            'results': results
        })
    
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        return JsonResponse({'error': str(e)})
