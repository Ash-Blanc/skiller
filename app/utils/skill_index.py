"""Local on-disk index for skill profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
import json

from app.models.skill import SkillProfile


INDEX_FILENAME = ".skill_index.json"


@dataclass(frozen=True)
class SkillIndexEntry:
    """Serializable cached representation of a saved skill profile."""

    skill_name: str
    skill_path: str
    person_name: str
    x_handle: str
    core_expertise: tuple[str, ...]
    unique_insights: tuple[str, ...]
    communication_style: str
    agent_instructions: str
    sample_posts: tuple[str, ...]
    search_text: str
    mtime: float

    @classmethod
    def from_profile(cls, profile: SkillProfile, skill_path: str, mtime: float) -> "SkillIndexEntry":
        skill_path_obj = Path(skill_path)
        return cls(
            skill_name=skill_path_obj.parent.name,
            skill_path=str(skill_path_obj),
            person_name=profile.person_name,
            x_handle=profile.x_handle,
            core_expertise=tuple(profile.core_expertise),
            unique_insights=tuple(profile.unique_insights),
            communication_style=profile.communication_style,
            agent_instructions=profile.agent_instructions,
            sample_posts=tuple(profile.sample_posts),
            search_text=" ".join(
                [
                    profile.person_name,
                    profile.x_handle,
                    " ".join(profile.core_expertise),
                    " ".join(profile.unique_insights),
                    profile.communication_style,
                    profile.agent_instructions,
                    " ".join(profile.sample_posts),
                ]
            ).lower(),
            mtime=mtime,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillIndexEntry":
        return cls(
            skill_name=str(data.get("skill_name", "")),
            skill_path=str(data.get("skill_path", "")),
            person_name=str(data.get("person_name", "")),
            x_handle=str(data.get("x_handle", "")),
            core_expertise=tuple(str(item) for item in data.get("core_expertise", [])),
            unique_insights=tuple(str(item) for item in data.get("unique_insights", [])),
            communication_style=str(data.get("communication_style", "")),
            agent_instructions=str(data.get("agent_instructions", "")),
            sample_posts=tuple(str(item) for item in data.get("sample_posts", [])),
            search_text=str(data.get("search_text", "")).lower(),
            mtime=float(data.get("mtime", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "skill_path": self.skill_path,
            "person_name": self.person_name,
            "x_handle": self.x_handle,
            "core_expertise": list(self.core_expertise),
            "unique_insights": list(self.unique_insights),
            "communication_style": self.communication_style,
            "agent_instructions": self.agent_instructions,
            "sample_posts": list(self.sample_posts),
            "search_text": self.search_text,
            "mtime": self.mtime,
        }

    def to_profile(self) -> SkillProfile:
        return SkillProfile(
            person_name=self.person_name,
            x_handle=self.x_handle,
            core_expertise=list(self.core_expertise),
            unique_insights=list(self.unique_insights),
            communication_style=self.communication_style,
            agent_instructions=self.agent_instructions,
            sample_posts=list(self.sample_posts),
        )


def skill_index_path(skills_dir: str | Path) -> Path:
    return Path(skills_dir) / INDEX_FILENAME


@lru_cache(maxsize=32)
def _load_cached_index(index_file: str, index_mtime: float) -> tuple[SkillIndexEntry, ...]:
    payload = json.loads(Path(index_file).read_text(encoding="utf-8"))
    entries = payload.get("skills", [])
    if not isinstance(entries, list):
        return ()
    return tuple(
        SkillIndexEntry.from_dict(entry)
        for entry in entries
        if isinstance(entry, dict)
    )


def load_skill_index_entries(skills_dir: str | Path) -> list[SkillIndexEntry]:
    """Load cached skill entries from the local index file."""
    index_file = skill_index_path(skills_dir)
    if not index_file.exists():
        return []

    try:
        index_mtime = index_file.stat().st_mtime
        return list(_load_cached_index(str(index_file), index_mtime))
    except Exception:
        return []


def save_skill_index_entries(
    skills_dir: str | Path,
    entries: Iterable[SkillIndexEntry],
) -> Path:
    """Persist the local skill index and clear stale caches."""
    index_file = skill_index_path(skills_dir)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skills": [entry.to_dict() for entry in entries],
    }
    index_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _load_cached_index.cache_clear()
    return index_file


def upsert_skill_index_entry(
    skills_dir: str | Path,
    profile: SkillProfile,
    skill_md_path: str | Path,
) -> Path:
    """Add or replace one skill entry in the local index."""
    skill_md_path = Path(skill_md_path)
    entries = load_skill_index_entries(skills_dir)
    entry = SkillIndexEntry.from_profile(
        profile=profile,
        skill_path=str(skill_md_path),
        mtime=skill_md_path.stat().st_mtime if skill_md_path.exists() else 0.0,
    )

    updated_entries = [existing for existing in entries if existing.skill_path != entry.skill_path]
    updated_entries.append(entry)
    return save_skill_index_entries(skills_dir, updated_entries)
