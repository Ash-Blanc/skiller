"""Shared helpers for loading prompt assets from the local registry."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import json

import yaml


@dataclass(frozen=True)
class PromptConfig:
    """Minimal local prompt config used by the app."""

    name: str
    model: str | None
    temperature: float | None
    messages: tuple[dict[str, Any], ...]
    prompt: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _prompt_registry() -> dict[str, str]:
    registry_path = _project_root() / "prompts.json"
    if not registry_path.exists():
        raise RuntimeError(f"Prompt registry not found: {registry_path}")
    return json.loads(registry_path.read_text(encoding="utf-8")).get("prompts", {})


def _resolve_prompt_path(prompt_name: str) -> Path:
    registry = _prompt_registry()
    if prompt_name not in registry:
        raise RuntimeError(f"Prompt '{prompt_name}' is not configured")

    entry = registry[prompt_name]
    if not isinstance(entry, str) or not entry.startswith("file:"):
        raise RuntimeError(f"Prompt '{prompt_name}' has unsupported registry entry")

    prompt_path = _project_root() / entry.removeprefix("file:")
    if not prompt_path.exists():
        raise RuntimeError(f"Prompt file not found for '{prompt_name}': {prompt_path}")
    return prompt_path


def _build_prompt_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages", [])
    system_messages = [
        str(message.get("content", "")).strip()
        for message in messages
        if isinstance(message, dict) and message.get("role") == "system"
    ]
    if system_messages:
        return "\n\n".join(message for message in system_messages if message)

    return "\n\n".join(
        str(message.get("content", "")).strip()
        for message in messages
        if isinstance(message, dict) and message.get("content")
    )


@lru_cache(maxsize=None)
def get_prompt_config(prompt_name: str) -> PromptConfig:
    """Return the local prompt config for a registered prompt."""
    prompt_path = _resolve_prompt_path(prompt_name)
    payload = yaml.safe_load(prompt_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise RuntimeError(f"Prompt '{prompt_name}' must contain a mapping")

    return PromptConfig(
        name=prompt_name,
        model=payload.get("model"),
        temperature=payload.get("temperature"),
        messages=tuple(
            message for message in payload.get("messages", []) if isinstance(message, dict)
        ),
        prompt=_build_prompt_text(payload),
    )


def get_prompt_text(prompt_name: str) -> str:
    """Return the system prompt text for a registered prompt."""
    return get_prompt_config(prompt_name).prompt
