from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import concurrent.futures
import os
import re

import yaml
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.mistral import MistralChat

from app.models.skill import SkillProfile
from app.models.session import (
    PersonaTurn,
    SessionConfig,
    SessionExecutionResult,
    SessionHistoryResponse,
    SessionPersona,
    SessionRecord,
    SessionSynthesisOutput,
    SessionTurn,
)
from app.tools.web_search_tool import WebSearchToolkit
from app.utils.skill_index import (
    SkillIndexEntry,
    load_skill_index_entries,
    save_skill_index_entries,
)
from app.utils.prompts import get_prompt_text
from app.utils.session_store import TeamSessionStore


_WORD_RE = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class ExpertSkillAssignment:
    """A single skill slice assigned to a persona agent."""

    profile: SkillProfile
    skill_focus: str
    relevance_score: float


@dataclass(frozen=True)
class ExpertResponse:
    """Response returned by one expert sub-agent."""

    profile: SkillProfile
    skill_focus: str
    response_text: str


@dataclass(frozen=True)
class ResearchContext:
    """Grounding context collected from web tools before ideation-heavy tasks."""

    required: bool
    available: bool
    summary: str


class SkillOrchestrator:
    def __init__(
        self,
        model_id: str = "mistral-large-latest",
        skills_dir: str = "skills",
        use_rag: bool = False,
        top_k_experts: int = 3,
        max_skill_agents_per_expert: int = 3,
        session_db_path: str = "data/skiller_sessions.db",
    ):
        """
        Initialize the Skill Orchestrator.

        Args:
            model_id: The Mistral model to use
            skills_dir: Directory containing skill files
            use_rag: Whether to use RAG-based skill search (recommended)
            top_k_experts: Number of top experts to consult for each task
            max_skill_agents_per_expert: Cap on the number of skill agents per expert
        """
        self.model_id = model_id
        self.skills_dir = skills_dir
        self.use_rag = use_rag
        self.top_k_experts = top_k_experts
        self.max_skill_agents_per_expert = max_skill_agents_per_expert
        self.session_db_path = session_db_path
        self.candidate_pool_size = max(8, top_k_experts * 4)
        self.prompt_text = get_prompt_text("skill_orchestrator")
        self.session_prompt_text = get_prompt_text("session_coordinator") or self.prompt_text

        os.makedirs(self.skills_dir, exist_ok=True)
        self.knowledge = None
        self.web_search = WebSearchToolkit()
        self.session_store = TeamSessionStore(db_path=self.session_db_path)
        self.session_db = SqliteDb(db_file=self.session_db_path)
        # Pre-initialize tables to avoid race conditions during parallel execution
        try:
            self.session_db._create_all_tables()
        except Exception:
            pass

        # Reused fallback agent for empty skill directories or synthesis failures.
        self.selector_agent = Agent(
            model=MistralChat(id=self.model_id),
            instructions=self._build_instructions(),
            tools=[self.web_search],
            markdown=True,
        )

    def _task_requires_grounding(self, task: str) -> bool:
        lowered = task.lower()
        grounding_signals = (
            "find me",
            "ideas",
            "novel",
            "interesting",
            "hackathon",
            "trends",
            "latest",
            "recent",
            "what are people building",
            "what's new",
            "what is new",
        )
        return any(signal in lowered for signal in grounding_signals)

    def _collect_research_context(self, task: str) -> ResearchContext:
        if not self._task_requires_grounding(task):
            return ResearchContext(
                required=False,
                available=False,
                summary="No mandatory live research required for this task.",
            )

        web_results = self.web_search.search_web(task, limit=5)
        news_results = self.web_search.search_news(task, limit=3)
        unavailable_markers = (
            "No web search backend available",
            "No web scraping backend available",
        )
        combined = "\n\n".join(
            [
                f"Web search:\n{web_results}",
                f"News search:\n{news_results}",
            ]
        ).strip()
        available = combined != "" and not any(marker in combined for marker in unavailable_markers)
        if not available:
            return ResearchContext(
                required=True,
                available=False,
                summary=(
                    "Live web grounding was required for this task, but no working search backend "
                    "returned evidence. Do not invent specifics, novelty claims, or ecosystem facts."
                ),
            )

        return ResearchContext(
            required=True,
            available=True,
            summary=combined,
        )

    def _build_agent(
        self,
        *,
        instructions: str,
        session_id: Optional[str] = None,
        output_schema: Optional[type] = None,
    ) -> Agent:
        kwargs = {
            "model": MistralChat(id=self.model_id),
            "instructions": instructions,
            "tools": [self.web_search],
            "markdown": True,
            "db": self.session_db,
            "add_history_to_context": True,
            "num_history_runs": 5,
        }
        if session_id:
            kwargs["session_id"] = session_id
        if output_schema is not None:
            kwargs["output_schema"] = output_schema
        return Agent(**kwargs)

    def _build_instructions(self) -> str:
        """Build agent instructions based on configuration."""
        base_prompt = self.prompt_text or "You are the Skill Orchestrator."

        rag_instructions = ""
        if self.use_rag:
            rag_instructions = f"""
You have access to a skill network built from the user's X connections.
Use the most relevant skills, but do not invent experts.
When multiple experts are relevant, coordinate them as a team and merge their outputs.
Focus on task execution.
"""

        return f"""
{base_prompt}

You have access to specialized expert skills loaded from {self.skills_dir}.
{rag_instructions}
Focus on TASK EXECUTION. If you receive expert notes, synthesize them into a direct answer.
"""

    def _skill_files(self) -> List[Path]:
        return sorted(Path(self.skills_dir).glob("*/SKILL.md"))

    def _skill_file_for_entry(self, entry: SkillIndexEntry) -> Path:
        return Path(entry.skill_path)

    def _split_frontmatter(self, text: str) -> tuple[dict, str]:
        if not text.startswith("---"):
            return {}, text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text

        _, frontmatter_text, body = parts
        try:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except Exception:
            frontmatter = {}
        return frontmatter, body

    def _extract_section(self, body: str, heading: str) -> str:
        pattern = rf"^## {re.escape(heading)}\s*(.*?)(?=^## |\Z)"
        match = re.search(pattern, body, flags=re.MULTILINE | re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    def _extract_bullets(self, section_text: str) -> List[str]:
        items = []
        for line in section_text.splitlines():
            cleaned = line.strip()
            if cleaned.startswith("- "):
                items.append(cleaned[2:].strip())
            elif cleaned:
                items.append(cleaned)
        return [item for item in items if item]

    def _parse_skill_profile(self, skill_path: Path) -> Optional[SkillProfile]:
        try:
            text = skill_path.read_text(encoding="utf-8")
        except Exception:
            return None

        frontmatter, body = self._split_frontmatter(text)
        metadata = frontmatter.get("metadata", {}) if isinstance(frontmatter, dict) else {}

        person_name = (
            metadata.get("person_name")
            or frontmatter.get("description", "").split(" (@")[0].replace("Expertise, communication style, and unique insights of ", "").strip()
            or skill_path.parent.name
        )
        x_handle = metadata.get("x_handle") or f"@{skill_path.parent.name}"

        core_expertise = self._extract_bullets(self._extract_section(body, "Core Expertise"))
        unique_insights = self._extract_bullets(self._extract_section(body, "Unique Insights"))
        communication_style = self._extract_section(body, "Communication Style") or "Clear, direct, and practical"
        agent_instructions = self._extract_section(body, "Instructions for the Agent") or (
            "Use the person's expertise to solve the task accurately and concretely."
        )
        sample_posts = self._extract_bullets(self._extract_section(body, "Sample Posts"))

        if not core_expertise and isinstance(metadata.get("core_expertise"), list):
            core_expertise = [str(item) for item in metadata["core_expertise"]]

        return SkillProfile(
            person_name=person_name or skill_path.parent.name,
            x_handle=x_handle,
            core_expertise=core_expertise,
            unique_insights=unique_insights,
            communication_style=communication_style,
            agent_instructions=agent_instructions,
            sample_posts=sample_posts,
        )

    def _rebuild_skill_entries_from_files(self) -> List[SkillIndexEntry]:
        entries: List[SkillIndexEntry] = []
        for skill_file in self._skill_files():
            profile = self._parse_skill_profile(skill_file)
            if profile is None:
                continue
            entries.append(
                SkillIndexEntry.from_profile(
                    profile=profile,
                    skill_path=str(skill_file),
                    mtime=skill_file.stat().st_mtime,
                )
            )

        save_skill_index_entries(self.skills_dir, entries)
        return entries

    def _load_skill_entries(self) -> List[SkillIndexEntry]:
        entries = load_skill_index_entries(self.skills_dir)
        if entries:
            return entries
        return self._rebuild_skill_entries_from_files()

    def _load_skill_profiles(self) -> List[SkillProfile]:
        return [entry.to_profile() for entry in self._load_skill_entries()]

    def _tokenize(self, text: str) -> set[str]:
        return set(_WORD_RE.findall(text.lower()))

    def _task_relevance_score(self, task: str, profile: SkillProfile) -> float:
        task_tokens = self._tokenize(task)
        if not task_tokens:
            return 0.0

        skill_text = " ".join(
            [
                profile.person_name,
                profile.x_handle,
                " ".join(profile.core_expertise),
                " ".join(profile.unique_insights),
                profile.communication_style,
                profile.agent_instructions,
            ]
        )
        skill_tokens = self._tokenize(skill_text)
        overlap = task_tokens & skill_tokens

        if not overlap:
            return 0.05 if profile.core_expertise else 0.0

        coverage = len(overlap) / max(1, len(task_tokens))
        density = len(overlap) / max(1, len(skill_tokens))
        handle_bonus = 0.05 if profile.x_handle.lower().lstrip("@") in task.lower() else 0.0
        return min(1.0, coverage * 0.7 + density * 0.25 + handle_bonus)

    def _entry_relevance_score(self, task: str, entry: SkillIndexEntry) -> float:
        task_tokens = self._tokenize(task)
        if not task_tokens:
            return 0.0

        entry_tokens = self._tokenize(entry.search_text)
        overlap = task_tokens & entry_tokens
        if not overlap:
            return 0.05 if entry.core_expertise else 0.0

        coverage = len(overlap) / max(1, len(task_tokens))
        density = len(overlap) / max(1, len(entry_tokens))
        handle_bonus = 0.05 if entry.x_handle.lower().lstrip("@") in task.lower() else 0.0
        return min(1.0, coverage * 0.7 + density * 0.25 + handle_bonus)

    def _rank_skill_entries(self, task: str, entries: List[SkillIndexEntry]) -> List[SkillIndexEntry]:
        ranked = sorted(
            entries,
            key=lambda entry: (
                self._entry_relevance_score(task, entry),
                len(entry.core_expertise),
                len(entry.unique_insights),
            ),
            reverse=True,
        )
        return ranked[: self.candidate_pool_size]

    def _rank_profiles(self, task: str, profiles: List[SkillProfile]) -> List[SkillProfile]:
        ranked = sorted(
            profiles,
            key=lambda profile: (
                self._task_relevance_score(task, profile),
                len(profile.core_expertise),
                len(profile.unique_insights),
            ),
            reverse=True,
        )
        return ranked[: self.top_k_experts]

    def _rank_skill_foci(self, task: str, profile: SkillProfile) -> List[ExpertSkillAssignment]:
        task_tokens = self._tokenize(task)
        assignments: List[ExpertSkillAssignment] = []

        scored_skills = []
        for skill in profile.core_expertise:
            skill_tokens = self._tokenize(skill)
            overlap = task_tokens & skill_tokens
            if overlap:
                score = len(overlap) / max(1, len(skill_tokens))
            else:
                skill_overlap = len(task_tokens & self._tokenize(" ".join(profile.unique_insights)))
                score = 0.25 if skill_overlap else 0.1
            scored_skills.append((skill, score))

        scored_skills.sort(key=lambda item: item[1], reverse=True)
        selected = scored_skills[: self.max_skill_agents_per_expert] if scored_skills else []

        for skill, score in selected:
            assignments.append(
                ExpertSkillAssignment(
                    profile=profile,
                    skill_focus=skill,
                    relevance_score=round(min(1.0, score), 3),
                )
            )

        return assignments

    def _session_config(self) -> SessionConfig:
        return SessionConfig(
            skills_dir=self.skills_dir,
            model_id=self.model_id,
            top_k_experts=self.top_k_experts,
            max_skill_agents_per_expert=self.max_skill_agents_per_expert,
            use_rag=self.use_rag,
        )

    def _persona_from_assignment(self, assignment: ExpertSkillAssignment) -> SessionPersona:
        persona = SessionPersona.from_skill_profile(assignment.profile)
        return persona.model_copy(
            update={
                "skill_focus": assignment.skill_focus,
                "relevance_score": assignment.relevance_score,
            }
        )

    def _build_session_personas(self, task: str) -> List[SessionPersona]:
        assignments = self._build_team_assignments(task)
        return [self._persona_from_assignment(assignment) for assignment in assignments]

    def _session_history_text(self, session: SessionRecord, recent_turns: List[SessionTurn]) -> str:
        if not recent_turns:
            history_text = "No prior turns."
        else:
            history_text = "\n\n".join(
                f"Turn {turn.turn_id}: {turn.task}\nAnswer: {turn.answer}"
                for turn in recent_turns
            )

        summary = session.summary.strip() or "No rolling summary yet."
        return f"""Session ID: {session.session_id}
Session title: {session.title}
Rolling summary: {summary}

Recent turns:
{history_text}
"""

    def _build_session_assignments(
        self,
        task: str,
        personas: List[SessionPersona],
    ) -> List[ExpertSkillAssignment]:
        assignments: List[ExpertSkillAssignment] = []
        for persona in personas:
            profile = persona.to_skill_profile()
            ranked = self._rank_skill_foci(task, profile)
            if ranked:
                assignments.append(ranked[0])
                continue
            assignments.append(
                ExpertSkillAssignment(
                    profile=profile,
                    skill_focus=persona.skill_focus or "General support",
                    relevance_score=persona.relevance_score,
                )
            )
        return assignments

    def _create_or_load_session(
        self,
        task: str,
        session_id: Optional[str],
        new_conversation: bool,
    ) -> tuple[SessionRecord, bool]:
        if session_id and new_conversation:
            raise ValueError("session_id and new_conversation are mutually exclusive")

        existing_session = self.session_store.get_session(session_id) if session_id else None
        if existing_session is not None and not new_conversation:
            return existing_session, False

        personas = self._build_session_personas(task)
        session = self.session_store.create_session(
            seed_task=task,
            config=self._session_config(),
            personas=personas,
            session_id=session_id if session_id and not new_conversation else None,
            title=task[:80].strip() or "Skiller Session",
        )
        return session, True

    def _agent_session_id(self, session_id: str, x_handle: str) -> str:
        handle = x_handle.lstrip("@").lower()
        return f"{session_id}:{handle}"

    def _build_team_assignments(self, task: str) -> List[ExpertSkillAssignment]:
        entries = self._load_skill_entries()
        if not entries:
            return []

        shortlisted_entries = self._rank_skill_entries(task, entries)
        top_profiles = [entry.to_profile() for entry in shortlisted_entries[: self.top_k_experts]]
        assignments: List[ExpertSkillAssignment] = []
        for profile in top_profiles:
            assignments.extend(self._rank_skill_foci(task, profile))

        # Keep the highest-priority assignments first.
        assignments.sort(key=lambda item: item.relevance_score, reverse=True)
        return assignments

    def refresh_skill_index(self) -> int:
        """Rebuild the local skill index from SKILL.md files."""
        return len(self._rebuild_skill_entries_from_files())

    def _build_persona_instructions(
        self,
        task: str,
        assignment: ExpertSkillAssignment,
        session_context: str = "",
        research_context: Optional[ResearchContext] = None,
    ) -> str:
        research_summary = research_context.summary if research_context else "No external research provided."
        grounding_rules = ""
        if research_context and research_context.required:
            grounding_rules = """
- Use the supplied web research context to ground your answer.
- Only call something novel, current, or interesting if the research context supports it.
- If the research context is unavailable or weak, explicitly say so instead of guessing.
"""
        return f"""
You are acting as {assignment.profile.person_name} ({assignment.profile.x_handle}).

Expert persona:
- Core expertise: {", ".join(assignment.profile.core_expertise) if assignment.profile.core_expertise else "Not specified"}
- Unique insights: {", ".join(assignment.profile.unique_insights) if assignment.profile.unique_insights else "Not specified"}
- Communication style: {assignment.profile.communication_style}

Focus skill for this agent:
- {assignment.skill_focus}

Persona instructions:
{assignment.profile.agent_instructions}

Task:
{task}

Session context:
{session_context or "No prior session context."}

Research context:
{research_summary}

Instructions:
- Solve only the portion of the task that best fits the focus skill.
- Be concrete and concise.
- Return the answer as if you were this expert, but do not claim certainty without evidence.
{grounding_rules}
""".strip()

    def _run_persona_assignment(
        self,
        task: str,
        assignment: ExpertSkillAssignment,
        session_context: str = "",
        session_id: Optional[str] = None,
        research_context: Optional[ResearchContext] = None,
    ) -> ExpertResponse:
        agent = self._build_agent(
            instructions=self._build_persona_instructions(
                task,
                assignment,
                session_context=session_context,
                research_context=research_context,
            ),
            session_id=session_id,
        )
        response = agent.run(task)
        response_text = response.content if hasattr(response, "content") else str(response)
        return ExpertResponse(
            profile=assignment.profile,
            skill_focus=assignment.skill_focus,
            response_text=response_text,
        )

    def _synthesize_team_responses(
        self,
        task: str,
        responses: List[ExpertResponse],
        session_context: str = "",
        session_id: Optional[str] = None,
        research_context: Optional[ResearchContext] = None,
    ) -> SessionSynthesisOutput:
        if not responses:
            fallback_prompt = task
            if research_context and research_context.required:
                fallback_prompt = (
                    f"Task: {task}\n\nResearch context:\n{research_context.summary}\n\n"
                    "Do not invent unsupported details."
                )
            response = self.selector_agent.run(fallback_prompt)
            fallback_answer = response.content if hasattr(response, "content") else str(response)
            return SessionSynthesisOutput(
                answer=fallback_answer,
                session_summary=session_context.strip() or fallback_answer[:240],
            )

        synthesis_agent = self._build_agent(
            instructions=self.session_prompt_text,
            session_id=session_id,
            output_schema=SessionSynthesisOutput,
        )

        expert_notes = "\n\n".join(
            f"### {response.profile.person_name} (@{response.profile.x_handle}) - {response.skill_focus}\n{response.response_text}"
            for response in responses
        )
        prompt = f"""Task: {task}

Session summary:
{session_context or "No prior session summary."}

Research context:
{research_context.summary if research_context else "No external research provided."}

Expert notes:
{expert_notes}

Write a direct answer and a concise rolling summary for the next turn.
If research grounding was required but unavailable, explicitly say that instead of claiming novelty or current relevance.
"""

        response = synthesis_agent.run(prompt)
        content = response.content if hasattr(response, "content") else response
        if isinstance(content, SessionSynthesisOutput):
            return content
        return SessionSynthesisOutput(
            answer=str(content),
            session_summary=session_context.strip() or str(content)[:240],
        )

    def _fallback_single_agent(self, task: str) -> str:
        response = self.selector_agent.run(task)
        return response.content if hasattr(response, "content") else str(response)

    def run_task(self, task: str) -> str:
        """
        Execute a task by spawning one agent per relevant skill across the top experts.

        The process is:
        1. Load skill profiles from disk.
        2. Rank the top experts for the task.
        3. Spawn one agent per relevant skill on those experts.
        4. Synthesize the team responses into a final answer.
        """
        result = self.run_session_task(task)
        return result.answer

    def run_session_task(
        self,
        task: str,
        session_id: Optional[str] = None,
        new_conversation: bool = False,
    ) -> SessionExecutionResult:
        """
        Execute a task using the initialized team personas and persist session history.
        """
        session, created_new_session = self._create_or_load_session(
            task=task,
            session_id=session_id,
            new_conversation=new_conversation,
        )
        recent_turns = self.session_store.get_recent_turns(session.session_id, limit=5)
        session_context = self._session_history_text(session, recent_turns)
        research_context = self._collect_research_context(task)

        if not session.personas:
            if research_context.required:
                answer = self._synthesize_team_responses(
                    task,
                    [],
                    session_context=session_context,
                    session_id=self._agent_session_id(session.session_id, "coordinator"),
                    research_context=research_context,
                ).answer
            else:
                answer = self._fallback_single_agent(task)
            turn = self.session_store.append_turn(
                session_id=session.session_id,
                task=task,
                answer=answer,
                persona_turns=[],
                session_summary=answer[:240],
            )
            return SessionExecutionResult(
                session_id=session.session_id,
                turn_id=turn.turn_id,
                created_new_session=created_new_session,
                answer=answer,
                summary=turn.session_summary,
                personas=session.personas,
                persona_turns=[],
            )

        assignments = self._build_session_assignments(task, session.personas)
        responses: List[ExpertResponse] = []
        max_workers = max(1, min(len(assignments), self.top_k_experts * self.max_skill_agents_per_expert))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for assignment in assignments:
                persona_session_id = self._agent_session_id(session.session_id, assignment.profile.x_handle)
                futures.append(
                    executor.submit(
                        self._run_persona_assignment,
                        task,
                        assignment,
                        session_context,
                        persona_session_id,
                        research_context,
                    )
                )
            for future in concurrent.futures.as_completed(futures):
                responses.append(future.result())

        responses.sort(
            key=lambda response: (
                self._task_relevance_score(task, response.profile),
                len(response.profile.core_expertise),
            ),
            reverse=True,
        )
        synthesis = self._synthesize_team_responses(
            task,
            responses,
            session_context=session_context,
            session_id=self._agent_session_id(session.session_id, "coordinator"),
            research_context=research_context,
        )
        if isinstance(synthesis, str):
            synthesis = SessionSynthesisOutput(
                answer=synthesis,
                session_summary=session_context.strip() or synthesis[:240],
            )

        persona_turns = [
            PersonaTurn(
                person_name=response.profile.person_name,
                x_handle=response.profile.x_handle,
                skill_focus=response.skill_focus,
                response_text=response.response_text,
                relevance_score=self._task_relevance_score(task, response.profile),
            )
            for response in responses
        ]
        turn = self.session_store.append_turn(
            session_id=session.session_id,
            task=task,
            answer=synthesis.answer,
            persona_turns=persona_turns,
            session_summary=synthesis.session_summary,
        )
        refreshed_session = self.session_store.get_session(session.session_id) or session
        return SessionExecutionResult(
            session_id=session.session_id,
            turn_id=turn.turn_id,
            created_new_session=created_new_session,
            answer=synthesis.answer,
            summary=synthesis.session_summary,
            personas=refreshed_session.personas,
            persona_turns=persona_turns,
        )

    def get_session_history(self, session_id: str) -> Optional[SessionHistoryResponse]:
        session = self.session_store.get_session(session_id)
        if session is None:
            return None
        return SessionHistoryResponse(session=session, turns=session.turns)
