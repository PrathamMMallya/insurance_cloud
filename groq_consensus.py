"""
Groq-based Multi-Agent Consensus System
For reaching mutual consensus on insurance/medical document analysis
"""

import os
import json
import time
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AgentRole(Enum):
    """Different agent roles in the consensus system"""
    ANALYZER = "analyzer"
    VALIDATOR = "validator"
    SYNTHESIZER = "synthesizer"
    CRITIC = "critic"


@dataclass
class ConsensusResult:
    """Result from consensus process"""
    final_decision: str
    confidence_score: float
    agent_positions: Dict[str, str]
    negotiation_rounds: int
    timestamp: datetime
    reasoning: str


class GroqConsensusAgent:
    """Individual agent in the consensus system"""
    
    def __init__(self, agent_id: str, role: AgentRole, model: str = "llama-3.1-8b-instant"):
        self.agent_id = agent_id
        self.role = role
        self.model = model
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.conversation_history = []
        self.position = None
        self.confidence = 0.0
    
    def analyze(self, context: str, query: str, previous_positions: Dict[str, str] = None) -> str:
        """Analyze context and provide position"""
        
        role_instructions = {
            AgentRole.ANALYZER: """You are an analytical agent. Your role is to thoroughly analyze the provided context 
and identify key facts, patterns, and insights. Be precise and evidence-based.""",
            AgentRole.VALIDATOR: """You are a validation agent. Your role is to verify claims, check consistency, 
and identify any logical fallacies or inconsistencies in the analysis.""",
            AgentRole.SYNTHESIZER: """You are a synthesis agent. Your role is to integrate different perspectives 
and find common ground between positions. Focus on building bridges.""",
            AgentRole.CRITIC: """You are a critical agent. Your role is to challenge assumptions, 
identify weaknesses, and push for higher standards of reasoning.""",
        }
        
        system_prompt = role_instructions[self.role]
        
        user_message = f"""Context to analyze:
{context}

Question/Task:
{query}

"""
        if previous_positions:
            user_message += f"Previous agent positions:\n"
            for agent_id, position in previous_positions.items():
                user_message += f"- {agent_id}: {position}\n"
            user_message += "\nConsider these positions in your analysis."
        
        user_message += f"\nProvide your analysis and position as {self.role.value}:"
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            response = message.content[0].text
            self.position = response
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            return response
        except Exception as e:
            logger.error(f"Error in agent {self.agent_id} analysis: {e}")
            return f"Error in analysis: {str(e)}"
    
    def evaluate_positions(self, positions: Dict[str, str], query: str) -> Tuple[str, float]:
        """Evaluate other agents' positions and provide feedback"""
        
        evaluation_prompt = f"""Based on the following positions on the question: "{query}"

Positions:
"""
        for agent_id, position in positions.items():
            evaluation_prompt += f"\n{agent_id}: {position}\n"
        
        evaluation_prompt += f"""
As a {self.role.value}, provide:
1. Your evaluation of these positions
2. Areas of agreement you see
3. Areas of disagreement
4. Your confidence level (0-1) in reaching consensus
5. Suggested compromise or synthesis"""
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": evaluation_prompt}
                ]
            )
            
            response = message.content[0].text
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Extract confidence score (simplified)
            if "confidence" in response.lower():
                try:
                    import re
                    confidence_match = re.search(r'confidence[:\s]+([0-9.]+)', response.lower())
                    if confidence_match:
                        self.confidence = float(confidence_match.group(1))
                except:
                    self.confidence = 0.7
            
            return response, self.confidence
        except Exception as e:
            logger.error(f"Error evaluating positions: {e}")
            return f"Error: {str(e)}", 0.0


class GroqConsensusSystem:
    """Multi-agent consensus system using Groq"""
    
    def __init__(self, num_agents: int = 4, max_rounds: int = 5):
        self.num_agents = num_agents
        self.max_rounds = max_rounds
        self.agents: List[GroqConsensusAgent] = []
        self.consensus_history = []
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Initialize agents with different roles"""
        roles = [
            AgentRole.ANALYZER,
            AgentRole.VALIDATOR,
            AgentRole.CRITIC,
            AgentRole.SYNTHESIZER
        ]
        
        for i in range(min(self.num_agents, len(roles))):
            agent = GroqConsensusAgent(
                agent_id=f"Agent-{roles[i].value.upper()}",
                role=roles[i]
            )
            self.agents.append(agent)
        
        logger.info(f"Initialized {len(self.agents)} consensus agents")
    
    def reach_consensus(self, context: str, query: str) -> ConsensusResult:
        """Run consensus process until mutual agreement or max rounds reached"""
        
        logger.info(f"Starting consensus process for query: {query}")
        all_positions = {}
        
        # Round 1: Initial analysis
        logger.info("Round 1: Initial analysis by all agents")
        for agent in self.agents:
            position = agent.analyze(context, query)
            all_positions[agent.agent_id] = position
            logger.info(f"{agent.agent_id} position provided")
        
        # Rounds 2+: Iterative refinement and consensus seeking
        for round_num in range(2, self.max_rounds + 1):
            logger.info(f"Round {round_num}: Consensus evaluation")
            
            convergence_scores = []
            refined_positions = {}
            
            for agent in self.agents:
                evaluation, confidence = agent.evaluate_positions(all_positions, query)
                convergence_scores.append(confidence)
                refined_positions[agent.agent_id] = evaluation
                
                # If agent feels confident, update position
                if confidence > 0.6:
                    agent.analyze(context, query, all_positions)
            
            all_positions.update(refined_positions)
            
            # Check consensus
            avg_confidence = sum(convergence_scores) / len(convergence_scores)
            logger.info(f"Round {round_num} average confidence: {avg_confidence:.2f}")
            
            if avg_confidence > 0.75:
                logger.info(f"Consensus reached at round {round_num} with confidence {avg_confidence:.2f}")
                break
            
            time.sleep(1)  # Rate limiting
        
        # Synthesize final consensus
        final_decision = self._synthesize_consensus(all_positions, query)
        
        result = ConsensusResult(
            final_decision=final_decision,
            confidence_score=avg_confidence,
            agent_positions=all_positions,
            negotiation_rounds=round_num,
            timestamp=datetime.now(),
            reasoning=self._generate_reasoning(all_positions)
        )
        
        self.consensus_history.append(result)
        return result
    
    def _synthesize_consensus(self, positions: Dict[str, str], query: str) -> str:
        """Synthesize final consensus from all agent positions"""
        
        synthesis_prompt = f"""Based on the following analysis and evaluations from multiple agents on: "{query}"

Agent Positions and Evaluations:
"""
        for agent_id, position in positions.items():
            synthesis_prompt += f"\n{agent_id}:\n{position}\n"
        
        synthesis_prompt += """
Please provide:
1. The areas of mutual consensus
2. The final synthesized decision that incorporates all perspectives
3. Key recommendations
4. Any remaining disagreements and how they were addressed

Provide a clear, concise final consensus statement."""
        
        try:
            message = self.client.messages.create(
                model="llama-3.1-8b-instant",
                max_tokens=2048,
                system="""You are a consensus synthesis expert. Your role is to read multiple perspectives, 
find common ground, and synthesize a unified decision that incorporates the best insights from all viewpoints.""",
                messages=[
                    {"role": "user", "content": synthesis_prompt}
                ]
            )
            
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error synthesizing consensus: {e}")
            return f"Error in synthesis: {str(e)}"
    
    def _generate_reasoning(self, positions: Dict[str, str]) -> str:
        """Generate explanation of how consensus was reached"""
        
        reasoning_prompt = f"""Analyze these agent positions and explain the consensus process:

Positions:
"""
        for agent_id, position in positions.items():
            reasoning_prompt += f"\n{agent_id}:\n{position}\n"
        
        reasoning_prompt += """
Provide a brief explanation of:
1. The consensus process that occurred
2. How agents converged
3. Key agreements reached"""
        
        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            message = client.messages.create(
                model="llama-3.1-8b-instant",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": reasoning_prompt}
                ]
            )
            
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error generating reasoning: {e}")
            return "Unable to generate reasoning"
    
    def get_consensus_json(self, result: ConsensusResult) -> str:
        """Convert consensus result to JSON"""
        
        return json.dumps({
            "final_decision": result.final_decision,
            "confidence_score": result.confidence_score,
            "negotiation_rounds": result.negotiation_rounds,
            "timestamp": result.timestamp.isoformat(),
            "reasoning": result.reasoning,
            "agent_positions": result.agent_positions
        }, indent=2)
    
    @property
    def client(self):
        """Groq client instance"""
        return Groq(api_key=os.getenv("GROQ_API_KEY"))


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize consensus system
    consensus_system = GroqConsensusSystem(num_agents=4, max_rounds=5)
    
    # Example context
    example_context = """
    Insurance Policy Document: Health Coverage Plan
    - Coverage: Hospitalization, Surgery, Medication
    - Age Limit: 18-65
    - Deductible: $1000
    - Co-insurance: 20%
    - Exclusions: Pre-existing conditions (first 2 years)
    """
    
    # Example query
    example_query = "Should a 45-year-old with controlled diabetes be covered under this plan?"
    
    # Run consensus
    result = consensus_system.reach_consensus(example_context, example_query)
    
    print("\n" + "="*80)
    print("CONSENSUS RESULT")
    print("="*80)
    print(f"Final Decision:\n{result.final_decision}")
    print(f"\nConfidence Score: {result.confidence_score:.2f}")
    print(f"Rounds Needed: {result.negotiation_rounds}")
    print("\n" + "="*80)
