from typing import List, Optional
from agno.agent import Agent
from agno.models.mistral import MistralChat
from app.models.skill import SkillProfile
from app.knowledge.skill_knowledge import get_shared_skill_knowledge
import langwatch
import os
import re

class SkillGenerator:
    def __init__(self, model_id: str = "mistral-large-latest"):
        self.model_id = model_id
        # Fetch the prompt from LangWatch
        self.prompt_config = langwatch.prompts.get("x_post_analyzer")
        
        self.agent = Agent(
            model=MistralChat(id=self.model_id),
            instructions=self.prompt_config.prompt,
            output_schema=SkillProfile,
            markdown=True
        )
        
        # Get shared knowledge base for indexing
        self.knowledge = get_shared_skill_knowledge()

    def generate_skill(self, person_name: str, x_handle: str, posts: str) -> Optional[SkillProfile]:
        """
        Generates a SkillProfile based on X posts.
        """
        response = self.agent.run(
            f"Please analyze the following posts from {person_name} (@{x_handle}) and extract their skill profile.\n\nPosts:\n{posts}",
        )
        return response.content

    def save_skill(self, profile: SkillProfile, skills_dir: str = "skills", index_in_kb: bool = True) -> str:
        """
        Saves a SkillProfile as an Agno Skill directory.
        
        Args:
            profile: The SkillProfile to save
            skills_dir: Directory to save skills
            index_in_kb: Whether to index in the knowledge base for RAG
            
        Returns:
            Path to the saved skill directory
        """
        # Create the skill name: lowercase, only letters, digits, and hyphens
        # Replace non-allowed characters with hyphens
        skill_name = profile.x_handle.replace("@", "").lower()
        skill_name = re.sub(r'[^a-z0-9-]', '-', skill_name)
        
        skill_path = os.path.join(skills_dir, skill_name)
        os.makedirs(skill_path, exist_ok=True)

        # Create SKILL.md with YAML frontmatter
        skill_md_path = os.path.join(skill_path, "SKILL.md")
        
        # Format the instructions
        # Allowed fields: ['allowed-tools', 'compatibility', 'description', 'license', 'metadata', 'name']
        content = f"""---
name: {skill_name}
description: Expertise, communication style, and unique insights of {profile.person_name} (@{profile.x_handle})
metadata:
  x_handle: "{profile.x_handle}"
  person_name: "{profile.person_name}"
  version: "1.0.0"
  core_expertise: {profile.core_expertise}
---

# {profile.person_name} (@{profile.x_handle})

## Core Expertise
{chr(10).join([f"- {item}" for item in profile.core_expertise])}

## Unique Insights
{chr(10).join([f"- {item}" for item in profile.unique_insights])}

## Communication Style
{profile.communication_style}

## Instructions for the Agent
{profile.agent_instructions}

## Sample Posts
{chr(10).join([f"- {post}" for post in profile.sample_posts])}
"""
        with open(skill_md_path, "w") as f:
            f.write(content)
        
        # Index in knowledge base for RAG retrieval
        if index_in_kb:
            self._index_skill(skill_md_path)
        
        return skill_path
    
    def _index_skill(self, skill_md_path: str):
        """
        Index a skill file in the knowledge base for RAG retrieval.
        """
        try:
            self.knowledge.add_content(path=skill_md_path)
        except Exception as e:
            print(f"   ⚠️ Warning: Could not index skill in knowledge base: {e}")

