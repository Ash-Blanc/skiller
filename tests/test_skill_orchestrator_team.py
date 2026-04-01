from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from app import main as main_module
from app.agents.orchestrator import (
    ExpertResponse,
    ResearchContext,
    SkillOrchestrator,
)
from app.models.skill import SkillProfile
from app.utils.prompts import get_prompt_text
from app.utils.skill_index import load_skill_index_entries, upsert_skill_index_entry


SKILL_TEMPLATE = """---
name: {name}
description: Expertise, communication style, and unique insights of {person_name} (@{x_handle})
metadata:
  x_handle: "{x_handle}"
  person_name: "{person_name}"
  version: "1.0.0"
  core_expertise: {core_expertise}
---

# {person_name} (@{x_handle})

## Core Expertise
{core_expertise_bullets}

## Unique Insights
{insight_bullets}

## Communication Style
{communication_style}

## Instructions for the Agent
{agent_instructions}

## Sample Posts
{sample_posts_bullets}
"""


def write_skill_file(
    root: Path,
    name: str,
    person_name: str,
    x_handle: str,
    core_expertise: list[str],
    unique_insights: list[str],
    communication_style: str,
    agent_instructions: str,
) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        SKILL_TEMPLATE.format(
            name=name,
            person_name=person_name,
            x_handle=x_handle,
            core_expertise=core_expertise,
            core_expertise_bullets="\n".join(f"- {item}" for item in core_expertise),
            insight_bullets="\n".join(f"- {item}" for item in unique_insights),
            communication_style=communication_style,
            agent_instructions=agent_instructions,
            sample_posts_bullets="- sample post one\n- sample post two",
        ),
        encoding="utf-8",
    )
    return skill_md


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    write_skill_file(
        tmp_path,
        name="alice-ml",
        person_name="Alice Chen",
        x_handle="@alicechen",
        core_expertise=["Machine Learning", "Python", "Evaluation"],
        unique_insights=["Small models can outperform if the data is cleaner."],
        communication_style="Practical and concise",
        agent_instructions="Focus on experiment design and evaluation.",
    )
    write_skill_file(
        tmp_path,
        name="bob-systems",
        person_name="Bob Singh",
        x_handle="@bobsingh",
        core_expertise=["Systems Design", "Distributed Systems", "Performance"],
        unique_insights=["Bottlenecks are often in coordination, not compute."],
        communication_style="Direct and analytical",
        agent_instructions="Focus on scalability and reliability.",
    )
    return tmp_path


def test_load_skill_profiles_parses_skill_files(skills_dir: Path):
    orchestrator = SkillOrchestrator(skills_dir=str(skills_dir), use_rag=False)

    profiles = orchestrator._load_skill_profiles()

    assert len(profiles) == 2
    assert {profile.person_name for profile in profiles} == {"Alice Chen", "Bob Singh"}
    assert any("Machine Learning" in profile.core_expertise for profile in profiles)


def test_skill_index_persists_profiles(tmp_path: Path):
    profile = SkillProfile(
        person_name="Alice Chen",
        x_handle="@alicechen",
        core_expertise=["Machine Learning", "Python"],
        unique_insights=["Cleaner data beats bigger models."],
        communication_style="Practical",
        agent_instructions="Focus on experiments.",
        sample_posts=["post one"],
    )
    skill_dir = tmp_path / "alice-ml"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("placeholder", encoding="utf-8")

    index_file = upsert_skill_index_entry(tmp_path, profile, skill_path)
    entries = load_skill_index_entries(tmp_path)

    assert index_file.exists()
    assert len(entries) == 1
    assert entries[0].person_name == "Alice Chen"
    assert "machine learning" in entries[0].search_text


def test_load_skill_profiles_uses_index_fast_path(skills_dir: Path):
    orchestrator = SkillOrchestrator(skills_dir=str(skills_dir), use_rag=False)
    orchestrator.refresh_skill_index()

    with patch.object(orchestrator, "_parse_skill_profile", side_effect=AssertionError("should not reparse indexed skills")):
        profiles = orchestrator._load_skill_profiles()

    assert len(profiles) == 2
    assert {profile.x_handle for profile in profiles} == {"@alicechen", "@bobsingh"}


def test_prompt_loader_uses_local_registry():
    prompt_text = get_prompt_text("skill_orchestrator")

    assert "Ultimate Generalist AI Orchestrator" in prompt_text
    assert "Do NOT invent experts or skills" in prompt_text


def test_run_task_spawns_one_agent_per_relevant_skill(skills_dir: Path):
    orchestrator = SkillOrchestrator(
        skills_dir=str(skills_dir),
        use_rag=False,
        top_k_experts=2,
        max_skill_agents_per_expert=2,
    )

    assignments_seen = []

    def fake_run_persona_assignment(
        task: str,
        assignment,
        session_context: str = "",
        session_id: str | None = None,
        research_context: ResearchContext | None = None,
    ):
        assignments_seen.append((assignment.profile.x_handle, assignment.skill_focus))
        return ExpertResponse(
            profile=assignment.profile,
            skill_focus=assignment.skill_focus,
            response_text=f"{assignment.profile.person_name} handled {assignment.skill_focus}",
        )

    with patch.object(orchestrator, "_run_persona_assignment", side_effect=fake_run_persona_assignment), \
         patch.object(orchestrator, "_synthesize_team_responses", return_value="FINAL TEAM ANSWER"):
        result = orchestrator.run_task("Plan a Python machine learning system with strong performance")

    assert result == "FINAL TEAM ANSWER"
    assert len(assignments_seen) >= 2
    assert any(skill == "Machine Learning" for _, skill in assignments_seen)
    assert any(skill == "Performance" for _, skill in assignments_seen)


def test_run_task_falls_back_when_no_skills(tmp_path: Path):
    orchestrator = SkillOrchestrator(skills_dir=str(tmp_path), use_rag=False)

    with patch.object(orchestrator.selector_agent, "run") as mock_run:
        mock_run.return_value.content = "fallback answer"
        result = orchestrator.run_task("Explain vector databases")

    assert result == "fallback answer"
    mock_run.assert_called_once()


def test_ideation_task_collects_grounding_context(skills_dir: Path):
    orchestrator = SkillOrchestrator(
        skills_dir=str(skills_dir),
        use_rag=False,
        top_k_experts=2,
        max_skill_agents_per_expert=2,
    )

    seen_research = []

    def fake_run_persona_assignment(
        task: str,
        assignment,
        session_context: str = "",
        session_id: str | None = None,
        research_context: ResearchContext | None = None,
    ):
        seen_research.append(research_context.summary if research_context else "")
        return ExpertResponse(
            profile=assignment.profile,
            skill_focus=assignment.skill_focus,
            response_text=f"{assignment.profile.person_name} handled {assignment.skill_focus}",
        )

    with patch.object(
        orchestrator,
        "_collect_research_context",
        return_value=ResearchContext(
            required=True,
            available=True,
            summary="Web search:\nGrounded search results",
        ),
    ), patch.object(orchestrator, "_run_persona_assignment", side_effect=fake_run_persona_assignment), \
         patch.object(orchestrator, "_synthesize_team_responses", return_value="FINAL TEAM ANSWER"):
        result = orchestrator.run_task("find me cool novel fun interesting ideas for claw4s hackathon")

    assert result == "FINAL TEAM ANSWER"
    assert seen_research
    assert all("Grounded search results" in item for item in seen_research)


def test_ideation_task_admits_missing_grounding(tmp_path: Path):
    orchestrator = SkillOrchestrator(skills_dir=str(tmp_path), use_rag=False)

    with patch.object(
        orchestrator,
        "_collect_research_context",
        return_value=ResearchContext(
            required=True,
            available=False,
            summary="Live web grounding was required for this task, but no working search backend returned evidence.",
        ),
    ), patch.object(orchestrator, "_synthesize_team_responses") as mock_synthesize:
        mock_synthesize.return_value = type(
            "Result",
            (),
            {
                "answer": "I can't verify novelty or current hackathon trends because no live search evidence was available.",
                "session_summary": "Grounding unavailable.",
            },
        )()
        result = orchestrator.run_task("find me cool novel fun interesting ideas for claw4s hackathon")

    assert "can't verify novelty" in result
    mock_synthesize.assert_called_once()


def test_execute_task_cli_forwards_team_configuration(monkeypatch, capsys):
    captured = {}

    class DummyOrchestrator:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_task(self, task: str) -> str:
            assert task == "Plan the launch"
            return "team result"

    monkeypatch.setattr(main_module, "SkillOrchestrator", DummyOrchestrator)

    main_module.execute_task(
        "Plan the launch",
        skills_dir="tmp-skills",
        model_id="mistral-small-latest",
        top_k_experts=4,
        max_skill_agents_per_expert=2,
        use_rag=False,
    )

    out = capsys.readouterr().out
    assert "team result" in out
    assert captured == {
        "model_id": "mistral-small-latest",
        "skills_dir": "tmp-skills",
        "use_rag": False,
        "top_k_experts": 4,
        "max_skill_agents_per_expert": 2,
        "session_db_path": "data/skiller_sessions.db",
    }
