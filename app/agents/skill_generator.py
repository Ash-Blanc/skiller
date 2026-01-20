from typing import List, Optional
from agno.agent import Agent
from agno.models.mistral import MistralChat
from app.models.skill import SkillProfile
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

    def generate_skill(self, person_name: str, x_handle: str, posts: str) -> Optional[SkillProfile]:
        """
        Generates a SkillProfile based on X posts.
        """
        response = self.agent.run(
            f"Please analyze the following posts from {person_name} (@{x_handle}) and extract their skill profile.\n\nPosts:\n{posts}",
        )
        return response.content

    def save_skill(self, profile: SkillProfile, skills_dir: str = "skills"):
        """
        Saves a SkillProfile as an Agno Skill directory.
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
        
        return skill_path
