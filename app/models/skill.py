from pydantic import BaseModel, Field
from typing import List, Optional

class SkillProfile(BaseModel):
    person_name: str = Field(..., description="The name of the person this skill is based on.")
    x_handle: str = Field(..., description="The X (Twitter) handle of the person.")
    core_expertise: List[str] = Field(..., description="List of core topics or fields they are experts in.")
    unique_insights: List[str] = Field(..., description="Novel takes, frameworks, or unique perspectives found in their posts.")
    communication_style: str = Field(..., description="Description of how they communicate (e.g., witty, technical, concise).")
    agent_instructions: str = Field(..., description="A set of system instructions to allow an AI to act as this person or use their expertise.")
    sample_posts: List[str] = Field(default_factory=list, description="A few high-quality posts that represent their style and knowledge.")
