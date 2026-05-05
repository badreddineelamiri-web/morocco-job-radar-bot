"""Validate jobs before publishing."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from date_parser import parse_date


OLD_TRACKER_PATH = Path("data/published_jobs.json")
SUSPICIOUS_WORDS = (
    "ربح سريع",
    "دخل يومي",
    "بدون مجهود",
    "salaire très élevé",
    "revenu garanti",
    "gain rapide",
    "crypto",
    "casino",
)


def job_identity(job: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(job.get("url") or job.get("application_url") or job.get("announcement_url") or "").strip().lower(),
            str(job.get("title") or job.get("job_title") or "").strip().lower(),
            str(job.get("organization") or job.get("company") or "").strip().lower(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def is_official_source(source: dict[str, Any]) -> bool:
    source_type = str(source.get("type", ""))
    return source_type in {"official_public", "official_ministry", "public_institution"}


def is_private_source(source: dict[str, Any]) -> bool:
    return str(source.get("category")) == "private_jobs" or str(source.get("type")).startswith("private")


def _state_published_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    items = state.get("published_jobs", [])
    return items if isinstance(items, list) else []


def _old_published_items() -> list[dict[str, Any]]:
    if not OLD_TRACKER_PATH.exists():
        return []
    try:
        data = json.loads(OLD_TRACKER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    return [item for item in data.values() if isinstance(item, dict)]


def already_published(job: dict[str, Any], state: dict[str, Any]) -> bool:
    identity = job_identity(job)
    url = str(job.get("url") or job.get("application_url") or job.get("announcement_url") or "").strip().lower()
    title = str(job.get("title") or job.get("job_title") or "").strip().lower()
    org = str(job.get("organization") or job.get("company") or "").strip().lower()
    for item in [*_state_published_items(state), *_old_published_items()]:
        item_id = str(item.get("id") or "").strip()
        item_url = str(item.get("url") or item.get("application_url") or item.get("announcement_url") or "").strip().lower()
        item_title = str(item.get("title") or "").strip().lower()
        item_org = str(item.get("organization") or item.get("company") or "").strip().lower()
        if item_id and item_id == identity:
            return True
        if url and item_url and url == item_url:
            return True
        if title and org and title == item_title and org == item_org:
            return True
    return False


def is_date_valid(job: dict[str, Any], source: dict[str, Any], today: dt.date | None = None) -> tuple[bool, str]:
    today = today or dt.date.today()
    deadline = parse_date(str(job.get("deadline") or ""))
    publication_date = parse_date(str(job.get("publication_date") or job.get("published_at") or ""))
    official = is_official_source(source)

    if deadline:
        if deadline < today:
            return False, f"deadline expired: {deadline.isoformat()}"
        return True, "deadline is current"

    if publication_date:
        max_age = 30 if official else 7
        if publication_date >= today - dt.timedelta(days=max_age):
            return True, f"publication date within {max_age} days"
        return False, f"publication date too old: {publication_date.isoformat()}"

    details_url = str(job.get("url") or job.get("announcement_url") or "").strip()
    source_page = str(job.get("source_page") or "").strip()
    if official and (job.get("pdf_url") or (details_url and details_url != source_page)):
        return True, "official source with details link"
    return False, "missing usable date"


def has_required_fields(job: dict[str, Any], source: dict[str, Any]) -> tuple[bool, str]:
    title = str(job.get("title") or job.get("job_title") or "").strip()
    url = str(job.get("url") or job.get("application_url") or job.get("announcement_url") or "").strip()
    description = str(job.get("description") or "").strip()
    if len(title) < 5:
        return False, "missing clear title"
    if not url.startswith(("http://", "https://")):
        return False, "missing official/details link"
    if is_private_source(source):
        city = str(job.get("city") or job.get("location") or "").strip()
        company = str(job.get("company") or job.get("organization") or "").strip()
        if not city or city.lower() in {"morocco", "maroc"}:
            return False, "private job missing city"
        if not company:
            return False, "private job missing employer"
        if len(description) < 25:
            return False, "private job missing useful details"
    return True, "required fields present"


def passes_private_safety(job: dict[str, Any], source: dict[str, Any]) -> tuple[bool, str]:
    if not is_private_source(source):
        return True, "not private"
    text = " ".join(str(job.get(key) or "") for key in ("title", "description", "application_method")).lower()
    if any(word.lower() in text for word in SUSPICIOUS_WORDS):
        return False, "suspicious private offer"
    if re.search(r"\b\d{5,}\s*(?:dh|mad|درهم)\b", text, re.IGNORECASE):
        return False, "unrealistic salary claim"
    if source.get("type") == "private_classifieds" and not job.get("application_method"):
        return False, "classified missing application method"
    return True, "private offer looks acceptable"


def validate_job(job: dict[str, Any], source: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
    checks = [
        has_required_fields(job, source),
        is_date_valid(job, source),
        passes_private_safety(job, source),
    ]
    for ok, reason in checks:
        if not ok:
            return False, reason
    if already_published(job, state):
        return False, "already published"
    return True, "valid"


def published_record(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job_identity(job),
        "title": job.get("title") or job.get("job_title"),
        "source": job.get("source") or job.get("source_name"),
        "organization": job.get("organization") or job.get("company"),
        "url": job.get("url") or job.get("application_url") or job.get("announcement_url"),
        "deadline": job.get("deadline"),
        "published_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
