from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.skill import SkillProfile


class SessionConfig(BaseModel):
    skills_dir: str = Field(..., description="Skills directory used for this session.")
    model_id: str = Field(..., description="Model id used for the session.")
    top_k_experts: int = Field(..., ge=1, description="Number of top experts selected.")
    max_skill_agents_per_expert: int = Field(..., ge=1, description="Maximum skill agents per expert.")
    use_rag: bool = Field(default=False, description="Whether RAG is enabled for the session.")


class SessionPersona(BaseModel):
    person_name: str
    x_handle: str
    core_expertise: List[str] = Field(default_factory=list)
    unique_insights: List[str] = Field(default_factory=list)
    communication_style: str = ""
    agent_instructions: str = ""
    skill_focus: str = ""
    relevance_score: float = 0.0

    @classmethod
    def from_skill_profile(cls, profile: SkillProfile) -> "SessionPersona":
        return cls(
            person_name=profile.person_name,
            x_handle=profile.x_handle,
            core_expertise=list(profile.core_expertise),
            unique_insights=list(profile.unique_insights),
            communication_style=profile.communication_style,
            agent_instructions=profile.agent_instructions,
        )

    def to_skill_profile(self) -> SkillProfile:
        return SkillProfile(
            person_name=self.person_name,
            x_handle=self.x_handle,
            core_expertise=list(self.core_expertise),
            unique_insights=list(self.unique_insights),
            communication_style=self.communication_style,
            agent_instructions=self.agent_instructions,
        )


class PersonaTurn(BaseModel):
    person_name: str
    x_handle: str
    skill_focus: str
    response_text: str
    relevance_score: float = 0.0


class SessionTurn(BaseModel):
    turn_id: int
    task: str
    answer: str
    created_at: datetime
    persona_turns: List[PersonaTurn] = Field(default_factory=list)
    session_summary: str = ""


class SessionRecord(BaseModel):
    session_id: str
    title: str
    seed_task: str
    summary: str = ""
    config: SessionConfig
    personas: List[SessionPersona] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    turns: List[SessionTurn] = Field(default_factory=list)


class SessionExecutionResult(BaseModel):
    session_id: str
    turn_id: int
    created_new_session: bool
    answer: str
    summary: str = ""
    personas: List[SessionPersona] = Field(default_factory=list)
    persona_turns: List[PersonaTurn] = Field(default_factory=list)


class SessionHistoryResponse(BaseModel):
    session: SessionRecord
    turns: List[SessionTurn] = Field(default_factory=list)


class SessionSynthesisOutput(BaseModel):
    answer: str
    session_summary: str
