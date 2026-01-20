from typing import Optional, List
from agno.agent import Agent
from agno.models.mistral import MistralChat
from agno.skills import Skills, LocalSkills
from agno.tools.knowledge import KnowledgeTools
from app.knowledge.skill_knowledge import get_shared_skill_knowledge
from app.models.skill import SkillProfile
import langwatch
import os


class SkillOrchestrator:
    def __init__(
        self, 
        model_id: str = "mistral-large-latest", 
        skills_dir: str = "skills",
        use_rag: bool = True
    ):
        """
        Initialize the Skill Orchestrator.
        
        Args:
            model_id: The Mistral model to use
            skills_dir: Directory containing skill files
            use_rag: Whether to use RAG-based skill search (recommended)
        """
        self.model_id = model_id
        self.skills_dir = skills_dir
        self.use_rag = use_rag
        self.prompt_config = langwatch.prompts.get("skill_orchestrator")
        
        # Ensure skills directory exists
        os.makedirs(self.skills_dir, exist_ok=True)
        
        # Load local skills
        self.skills = Skills(loaders=[LocalSkills(self.skills_dir)])
        
        # Setup tools based on configuration
        tools = []
        
        if use_rag:
            # Use KnowledgeTools for RAG-based skill retrieval
            self.knowledge = get_shared_skill_knowledge()
            self.knowledge_tools = KnowledgeTools(
                knowledge=self.knowledge,
                think=True,       # Enable planning/brainstorming
                search=True,      # Enable knowledge search
                analyze=True,     # Enable result analysis
                add_few_shot=True,  # Add examples for better results
            )
            tools.append(self.knowledge_tools)
        
        # Primary agent for searching and selecting the skill
        self.selector_agent = Agent(
            model=MistralChat(id=self.model_id),
            tools=tools if tools else None,
            skills=self.skills,
            instructions=self._build_instructions(),
            markdown=True
        )

    def _build_instructions(self) -> str:
        """Build agent instructions based on configuration."""
        base_prompt = self.prompt_config.prompt if self.prompt_config else "You are the Skill Orchestrator."
        
        rag_instructions = ""
        if self.use_rag:
            rag_instructions = """
You have access to a knowledge base of expert skills via the Knowledge Tools.
Use the Think → Search → Analyze cycle:
1. THINK: Plan your approach and identify key search terms
2. SEARCH: Query the knowledge base for relevant expert skills  
3. ANALYZE: Evaluate if the results are sufficient or if you need more searches

When you find the right expert, use their communication style and expertise to complete the task.
"""
        
        return f"""
{base_prompt}

You have access to specialized expert skills loaded from {self.skills_dir}.
Use 'get_skill_instructions(skill_name)' to explore available skills if needed.
{rag_instructions}
Your goal is to find the most relevant expert skill for a given task and execute it using their unique perspective and expertise.
"""

    def run_task(self, task: str) -> str:
        """
        Orchestrates the task by finding the best expert and executing it.
        
        Uses RAG-based knowledge retrieval to find the most relevant expert,
        then applies their expertise to complete the task.
        """
        response = self.selector_agent.run(task)
        return response.content

