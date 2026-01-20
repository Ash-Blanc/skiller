"""
State management for lazy/batch skill loading.
Tracks which profiles have been processed to avoid reprocessing.
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any

STATE_FILE = "data/network_state.json"


def _get_state_path() -> str:
    """Get absolute path to state file."""
    # Assumes we're running from project root
    return STATE_FILE


def load_network_state() -> Dict[str, Any]:
    """
    Load network state from disk.
    Returns empty state if file doesn't exist.
    """
    state_path = _get_state_path()
    if os.path.exists(state_path):
        with open(state_path, 'r') as f:
            return json.load(f)
    return {
        "following_handles": [],
        "processed_handles": [],
        "last_updated": None
    }


def save_network_state(state: Dict[str, Any]) -> None:
    """Save network state to disk."""
    state_path = _get_state_path()
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    state["last_updated"] = datetime.now().isoformat()
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)


def get_pending_handles(state: Dict[str, Any]) -> List[str]:
    """Get handles that haven't been processed yet."""
    following = set(state.get("following_handles", []))
    processed = set(state.get("processed_handles", []))
    return list(following - processed)


def mark_handle_processed(state: Dict[str, Any], handle: str) -> Dict[str, Any]:
    """Mark a handle as processed and return updated state."""
    if handle not in state.get("processed_handles", []):
        state.setdefault("processed_handles", []).append(handle)
    return state
