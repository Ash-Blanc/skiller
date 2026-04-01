from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents.orchestrator import ExpertResponse, SkillOrchestrator
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
from app.agents.orchestrator import ResearchContext
from app.utils.session_store import TeamSessionStore


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


def make_skills_dir(tmp_path: Path) -> Path:
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


def test_session_store_round_trip(tmp_path: Path):
    store = TeamSessionStore(db_path=str(tmp_path / "team_sessions.db"))
    config = SessionConfig(
        skills_dir="skills",
        model_id="mistral-large-latest",
        top_k_experts=2,
        max_skill_agents_per_expert=1,
        use_rag=False,
    )
    personas = [
        SessionPersona(
            person_name="Alice Chen",
            x_handle="@alicechen",
            core_expertise=["Machine Learning"],
            unique_insights=["Cleaner data beats bigger models."],
            communication_style="Practical",
            agent_instructions="Focus on experiments.",
            skill_focus="Machine Learning",
            relevance_score=0.95,
        )
    ]

    session = store.create_session(
        seed_task="Plan a model evaluation strategy",
        config=config,
        personas=personas,
        session_id="session-123",
    )
    turn = store.append_turn(
        session_id=session.session_id,
        task="Plan a model evaluation strategy",
        answer="Use holdout validation and A/B tests.",
        persona_turns=[
            PersonaTurn(
                person_name="Alice Chen",
                x_handle="@alicechen",
                skill_focus="Machine Learning",
                response_text="Use holdout validation and A/B tests.",
                relevance_score=0.95,
            )
        ],
        session_summary="Keep the rollout measurable and compare against a baseline.",
    )

    loaded = store.get_session("session-123")
    assert loaded is not None
    assert loaded.summary == "Keep the rollout measurable and compare against a baseline."
    assert loaded.personas[0].skill_focus == "Machine Learning"
    assert loaded.turns[0].turn_id == turn.turn_id
    assert loaded.turns[0].answer == "Use holdout validation and A/B tests."


def test_run_session_task_creates_and_reuses_session(tmp_path: Path):
    skills_dir = make_skills_dir(tmp_path)
    orchestrator = SkillOrchestrator(
        skills_dir=str(skills_dir),
        use_rag=False,
        top_k_experts=2,
        max_skill_agents_per_expert=2,
        session_db_path=str(tmp_path / "sessions.db"),
    )

    persona_calls: list[tuple[str | None, str, str]] = []

    def fake_run_persona_assignment(
        task: str,
        assignment,
        session_context: str = "",
        session_id: str | None = None,
        research_context: ResearchContext | None = None,
    ):
        persona_calls.append((session_id, assignment.profile.x_handle, assignment.skill_focus))
        return ExpertResponse(
            profile=assignment.profile,
            skill_focus=assignment.skill_focus,
            response_text=f"{assignment.profile.person_name} handled {assignment.skill_focus}",
        )

    def fake_synthesize(
        task: str,
        responses,
        session_context: str = "",
        session_id: str | None = None,
        research_context: ResearchContext | None = None,
    ):
        return SessionSynthesisOutput(
            answer=f"Final answer for: {task}",
            session_summary=f"Rolling summary for: {task}",
        )

    with patch.object(orchestrator, "_run_persona_assignment", side_effect=fake_run_persona_assignment), \
         patch.object(orchestrator, "_synthesize_team_responses", side_effect=fake_synthesize):
        first = orchestrator.run_session_task("Plan a deployment pipeline", new_conversation=True)

    assert first.created_new_session is True
    assert first.session_id
    assert first.answer == "Final answer for: Plan a deployment pipeline"
    assert persona_calls

    history = orchestrator.get_session_history(first.session_id)
    assert history is not None
    assert len(history.turns) == 1
    assert history.turns[0].answer == first.answer

    with patch.object(orchestrator, "_build_session_personas", side_effect=AssertionError("should reuse roster")), \
         patch.object(orchestrator, "_run_persona_assignment", side_effect=fake_run_persona_assignment), \
         patch.object(orchestrator, "_synthesize_team_responses", side_effect=fake_synthesize):
        second = orchestrator.run_session_task(
            "Add rollout safeguards and monitoring",
            session_id=first.session_id,
        )

    assert second.created_new_session is False
    assert second.session_id == first.session_id
    history = orchestrator.get_session_history(first.session_id)
    assert history is not None
    assert len(history.turns) == 2
    assert history.session.personas
    assert all(persona.skill_focus for persona in history.session.personas)


def test_execute_task_cli_uses_session_result(monkeypatch, capsys):
    captured = {}

    class DummyOrchestrator:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_session_task(self, task: str, session_id: str | None = None, new_conversation: bool = False):
            captured["call"] = (task, session_id, new_conversation)
            return SessionExecutionResult(
                session_id=session_id or "session-abc",
                turn_id=1,
                created_new_session=new_conversation,
                answer="session answer",
                summary="session summary",
                personas=[
                    SessionPersona(
                        person_name="Alice Chen",
                        x_handle="@alicechen",
                        core_expertise=["Machine Learning"],
                        unique_insights=[],
                        communication_style="Practical",
                        agent_instructions="Focus on experiments.",
                        skill_focus="Machine Learning",
                        relevance_score=0.95,
                    )
                ],
                persona_turns=[],
            )

    monkeypatch.setattr(main_module, "SkillOrchestrator", DummyOrchestrator)

    main_module.execute_task(
        "Plan the launch",
        skills_dir="tmp-skills",
        model_id="mistral-small-latest",
        top_k_experts=4,
        max_skill_agents_per_expert=2,
        use_rag=False,
        session_id="session-xyz",
        new_conversation=False,
        session_db_path="tmp-sessions.db",
    )

    out = capsys.readouterr().out
    assert "session answer" in out
    assert "session_id: session-xyz" not in out
    assert "session summary" not in out
    assert captured["call"] == ("Plan the launch", "session-xyz", False)


def test_execute_task_api_returns_session_metadata(monkeypatch):
    from app import os as os_module

    captured = {}

    class DummyOrchestrator:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_session_task(self, task: str, session_id: str | None = None, new_conversation: bool = False):
            captured["call"] = (task, session_id, new_conversation)
            return SessionExecutionResult(
                session_id="session-api-1",
                turn_id=3,
                created_new_session=True,
                answer="api answer",
                summary="api summary",
                personas=[
                    SessionPersona(
                        person_name="Bob Singh",
                        x_handle="@bobsingh",
                        core_expertise=["Systems Design"],
                        unique_insights=[],
                        communication_style="Direct",
                        agent_instructions="Focus on reliability.",
                        skill_focus="Systems Design",
                        relevance_score=0.91,
                    )
                ],
                persona_turns=[],
            )

    monkeypatch.setattr(os_module, "SkillOrchestrator", DummyOrchestrator)

    client = TestClient(os_module.app)
    response = client.post(
        "/api/execute-task",
        json={
            "task": "Plan the launch",
            "skills_dir": "tmp-skills",
            "model_id": "mistral-small-latest",
            "top_k_experts": 4,
            "max_skill_agents_per_expert": 2,
            "use_rag": False,
            "session_id": "session-api",
            "new_conversation": False,
            "session_db_path": "tmp-sessions.db",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == "api answer"
    assert payload["session_id"] == "session-api-1"
    assert payload["turn_id"] == 3
    assert payload["created_new_session"] is True
    assert payload["personas"][0]["skill_focus"] == "Systems Design"
    assert captured["call"] == ("Plan the launch", "session-api", False)


def test_session_history_endpoint(monkeypatch):
    from app import os as os_module

    history = SessionHistoryResponse(
        session=SessionRecord(
            session_id="session-hist-1",
            title="Plan launch",
            seed_task="Plan launch",
            summary="Rolling summary",
            config=SessionConfig(
                skills_dir="skills",
                model_id="mistral-large-latest",
                top_k_experts=2,
                max_skill_agents_per_expert=1,
                use_rag=False,
            ),
            personas=[
                SessionPersona(
                    person_name="Alice Chen",
                    x_handle="@alicechen",
                    core_expertise=["Machine Learning"],
                    unique_insights=[],
                    communication_style="Practical",
                    agent_instructions="Focus on experiments.",
                    skill_focus="Machine Learning",
                    relevance_score=0.95,
                )
            ],
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            turns=[],
        ),
        turns=[
            SessionTurn(
                turn_id=1,
                task="Plan launch",
                answer="Use a phased rollout.",
                created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                persona_turns=[],
                session_summary="Use a phased rollout.",
            )
        ],
    )

    class DummyOrchestrator:
        def __init__(self, **kwargs):
            pass

        def get_session_history(self, session_id: str):
            assert session_id == "session-hist-1"
            return history

    monkeypatch.setattr(os_module, "SkillOrchestrator", DummyOrchestrator)

    client = TestClient(os_module.app)
    response = client.get("/api/sessions/session-hist-1/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["session_id"] == "session-hist-1"
    assert payload["session"]["summary"] == "Rolling summary"
    assert payload["turns"][0]["answer"] == "Use a phased rollout."
