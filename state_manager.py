"""Read and write the round-robin source state."""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
STATE_PATH = Path("state/jobs_sources_state.json")


def default_state() -> dict[str, Any]:
    return {
        "last_source_index": -1,
        "published_jobs": [],
        "failed_sources": {},
        "last_run_at": None,
    }


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        state = default_state()
        save_state(state, path)
        return state
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.error("Could not read state file; using defaults: %s", exc)
        return default_state()

    state = default_state()
    if isinstance(data, dict):
        state.update(data)
    if not isinstance(state.get("published_jobs"), list):
        state["published_jobs"] = []
    if not isinstance(state.get("failed_sources"), dict):
        state["failed_sources"] = {}
    return state


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["last_run_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def update_last_source(state: dict[str, Any], index: int) -> None:
    state["last_source_index"] = index


def record_failed_source(state: dict[str, Any], source_name: str, error: str) -> None:
    failed = state.setdefault("failed_sources", {})
    previous = failed.get(source_name, {}) if isinstance(failed.get(source_name), dict) else {}
    failed[source_name] = {
        "last_error": str(error)[:500],
        "failed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "fail_count": int(previous.get("fail_count", 0)) + 1,
    }


def clear_failed_source(state: dict[str, Any], source_name: str) -> None:
    failed = state.setdefault("failed_sources", {})
    if source_name in failed:
        del failed[source_name]


def add_published_job(state: dict[str, Any], item: dict[str, Any], max_items: int = 1000) -> None:
    published = state.setdefault("published_jobs", [])
    published.insert(0, item)
    state["published_jobs"] = published[:max_items]
