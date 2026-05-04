"""Track published jobs to avoid duplicates."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
TRACKER_FILE = Path("data/published_jobs.json")
MAX_TRACKED_JOBS = 1000  # Keep only last 1000 jobs to avoid file getting too large


def _job_hash(job: dict[str, Any]) -> str:
    """Create a unique hash for a job based on title, company, and URL."""
    # Use multiple fields to create a unique identifier
    title = str(job.get("title") or "").strip().lower()
    company = str(job.get("company") or "").strip().lower()
    url = str(job.get("application_url") or job.get("url") or job.get("announcement_url") or "").strip()
    
    # Create hash from available fields
    hash_parts = []
    if title:
        hash_parts.append(f"title:{title}")
    if company:
        hash_parts.append(f"company:{company}")
    if url:
        hash_parts.append(f"url:{url}")
    
    # If we have at least 2 fields, use them; otherwise use whatever we have
    if len(hash_parts) >= 2:
        raw = "|".join(hash_parts)
    else:
        # Fallback: use all available data
        raw = "|".join([
            f"title:{title}",
            f"company:{company}",
            f"url:{url}",
            f"location:{job.get('location', '')}",
            f"description:{(job.get('description') or '')[:100]}"
        ])
    
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def load_published_jobs() -> dict[str, Any]:
    """Load the set of published job hashes."""
    if not TRACKER_FILE.exists():
        return {}
    
    try:
        data = json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.error("Could not load published jobs tracker: %s", exc)
        return {}


def save_published_jobs(published: dict[str, Any]) -> None:
    """Save the set of published job hashes."""
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Keep only the most recent jobs to avoid file getting too large
    if len(published) > MAX_TRACKED_JOBS:
        # Sort by timestamp and keep only the most recent
        sorted_jobs = sorted(
            published.items(),
            key=lambda x: x[1].get("published_at", "") if isinstance(x[1], dict) else "",
            reverse=True
        )
        published = dict(sorted_jobs[:MAX_TRACKED_JOBS])
    
    try:
        TRACKER_FILE.write_text(
            json.dumps(published, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except OSError as exc:
        LOGGER.error("Could not save published jobs tracker: %s", exc)


def is_job_published(job: dict[str, Any]) -> bool:
    """Check if a job has already been published."""
    published = load_published_jobs()
    job_hash = _job_hash(job)
    return job_hash in published


def mark_job_published(job: dict[str, Any], post_result: dict[str, Any] | None = None) -> None:
    """Mark a job as published."""
    published = load_published_jobs()
    job_hash = _job_hash(job)
    
    import datetime
    published[job_hash] = {
        "title": job.get("title"),
        "company": job.get("company"),
        "published_at": datetime.datetime.now().isoformat(),
        "post_result": post_result or {},
    }
    
    save_published_jobs(published)
    LOGGER.info(f"Marked job as published: {job.get('title')} (hash: {job_hash})")


def clean_old_jobs(days_to_keep: int = 30) -> int:
    """Remove jobs older than specified days. Returns number of removed jobs."""
    published = load_published_jobs()
    
    import datetime
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
    
    to_remove = []
    for job_hash, data in published.items():
        if isinstance(data, dict) and "published_at" in data:
            try:
                published_date = datetime.datetime.fromisoformat(data["published_at"])
                if published_date < cutoff_date:
                    to_remove.append(job_hash)
            except (ValueError, TypeError):
                continue
    
    for job_hash in to_remove:
        del published[job_hash]
    
    if to_remove:
        save_published_jobs(published)
        LOGGER.info(f"Cleaned {len(to_remove)} old jobs from tracker")
    
    return len(to_remove)


def get_published_count() -> int:
    """Get count of published jobs."""
    return len(load_published_jobs())
