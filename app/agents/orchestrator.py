from typing import Optional, List
from agno.agent import Agent
from agno.models.mistral import MistralChat
from agno.skills import Skills, LocalSkills
from app.tools.supermemory_tool import SupermemoryToolkit
from app.models.skill import SkillProfile
import langwatch
import json
import os

class SkillOrchestrator:
    def __init__(self, model_id: str = "mistral-large-latest", skills_dir: str = "skills"):
        self.model_id = model_id
        self.skills_dir = skills_dir
        self.supermemory_toolkit = SupermemoryToolkit()
        self.prompt_config = langwatch.prompts.get("skill_orchestrator")
        
        # Ensure skills directory exists
        os.makedirs(self.skills_dir, exist_ok=True)
        
        # Load skills
        self.skills = Skills(loaders=[LocalSkills(self.skills_dir)])
        
        # Primary agent for searching and selecting the skill
        self.selector_agent = Agent(
            model=MistralChat(id=self.model_id),
            tools=[self.supermemory_toolkit],
            skills=self.skills,
            instructions=f"""
            {self.prompt_config.prompt if self.prompt_config else "You are the Skill Selector."}
            
            You have access to specialized expert skills loaded from {self.skills_dir}.
            Use 'get_skill_instructions(skill_name)' to explore available skills if needed.
            
            Your goal is to find the most relevant expert skill for a given task.
            Search Supermemory or check available skills, evaluate the results, and decide which skill to use.
            """,
            markdown=True
        )

    def run_task(self, task: str) -> str:
        """
        Orchestrates the task by finding the best expert and executing it.
        """
        # Step 1: Select and execute using the skills system
        # Agno's Skills system allows the agent to discover and use skills automatically
        # if they are provided in the skills parameter.
        
        response = self.selector_agent.run(task)
        return response.content
