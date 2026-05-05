#!/usr/bin/env python3
"""Run one Morocco Job Radar round-robin cycle."""

from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Any

from facebook_formatter import format_facebook_post
from job_filter import published_record, validate_job
from modules.facebook_publisher import publish_job
from modules.image_maker import create_job_image
from modules.job_tracker import get_published_count, mark_job_published
from quality_gate import validate_image_quality, validate_post_quality
from scrapers import scraper_for
from sources import enabled_sources
from state_manager import (
    add_published_job,
    clear_failed_source,
    load_state,
    record_failed_source,
    save_state,
    update_last_source,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger("Main")


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        LOGGER.warning("Invalid %s value; using %d.", name, default)
        return default


def _dry_run_enabled() -> bool:
    return os.getenv("DRY_RUN", "true").strip().lower() in {"1", "true", "yes"}


def _facebook_credentials_ready() -> bool:
    return bool(os.getenv("FACEBOOK_PAGE_ID", "").strip() and os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip())


def _source_in_cooldown(state: dict[str, Any], source_name: str) -> bool:
    failed = state.get("failed_sources", {}).get(source_name, {})
    if not isinstance(failed, dict) or int(failed.get("fail_count", 0)) < 3:
        return False
    try:
        failed_at = dt.datetime.fromisoformat(str(failed.get("failed_at", "")))
    except ValueError:
        return False
    if failed_at.tzinfo is None:
        failed_at = failed_at.replace(tzinfo=dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc) - failed_at < dt.timedelta(hours=1)


def _ordered_indices(start_index: int, source_count: int) -> list[int]:
    return [(start_index + offset) % source_count for offset in range(source_count)]


def _valid_jobs_from_source(source: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    scraper = scraper_for(source)
    scraped_jobs = scraper.scrape()
    LOGGER.info("%s fetched %d job(s).", source["name"], len(scraped_jobs))
    valid_jobs: list[dict[str, Any]] = []
    for job in scraped_jobs:
        ok, reason = validate_job(job, source, state)
        if ok:
            valid_jobs.append(job)
        else:
            LOGGER.info("Skipped from %s: %s (%s)", source["name"], job.get("title"), reason)
    return valid_jobs


def _publish_or_print(job: dict[str, Any], state: dict[str, Any]) -> bool:
    post_data = format_facebook_post(job)
    post_ok, post_reason = validate_post_quality(post_data)
    if not post_ok:
        LOGGER.error("Post quality rejected for %s: %s", job.get("title"), post_reason)
        return False

    if _dry_run_enabled():
        LOGGER.info("DRY_RUN enabled; Facebook publish skipped.")
        print("\n" + "=" * 70)
        print("DRY RUN - POST PREVIEW")
        print("=" * 70)
        print(post_data["facebook_post"])
        print("\nFIRST COMMENT:")
        print(post_data["first_comment"])
        print("=" * 70 + "\n")
        return True

    image_path = create_job_image(job, post_data)
    image_ok, image_reason = validate_image_quality(image_path)
    if not image_ok:
        LOGGER.error("Image quality rejected for %s: %s", job.get("title"), image_reason)
        return False

    result = publish_job(post_data, image_path)
    if not result.get("ok"):
        LOGGER.error("Publish failed: %s", result.get("error", "unknown error"))
        return False

    mark_job_published(job, result)
    add_published_job(state, published_record(job))
    LOGGER.info("Published job: %s", job.get("title"))
    return True


def main() -> None:
    os.environ.setdefault("DRY_RUN", "true")
    if not _dry_run_enabled() and not _facebook_credentials_ready():
        raise SystemExit("FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN must be set for live publishing.")

    sources = enabled_sources()
    if not sources:
        LOGGER.warning("No enabled sources configured.")
        return

    state = load_state()
    max_jobs = _env_int("MAX_JOBS_PER_RUN", default=1)
    start_index = (int(state.get("last_source_index", -1)) + 1) % len(sources)
    published_count = 0
    checked_count = 0

    LOGGER.info("Starting round-robin at source index %d/%d.", start_index, len(sources) - 1)
    LOGGER.info("DRY_RUN=%s", _dry_run_enabled())

    for source_index in _ordered_indices(start_index, len(sources)):
        source = sources[source_index]
        checked_count += 1
        update_last_source(state, source_index)

        if _source_in_cooldown(state, source["name"]):
            LOGGER.warning("Skipping %s: in one-hour cooldown after repeated failures.", source["name"])
            save_state(state)
            continue

        LOGGER.info("Checking source: %s", source["name"])
        try:
            valid_jobs = _valid_jobs_from_source(source, state)
            clear_failed_source(state, source["name"])
        except Exception as exc:
            LOGGER.error("Source failed, moving on: %s - %s", source["name"], exc)
            record_failed_source(state, source["name"], str(exc))
            save_state(state)
            continue

        save_state(state)
        if not valid_jobs:
            LOGGER.info("No new valid job found in %s; moving to next source.", source["name"])
            continue

        for job in valid_jobs:
            if _publish_or_print(job, state):
                published_count += 1
                if not _dry_run_enabled():
                    save_state(state)
            if published_count >= max_jobs:
                LOGGER.info("Publish target reached: %d/%d.", published_count, max_jobs)
                save_state(state)
                LOGGER.info("Total published jobs in legacy tracker: %d", get_published_count())
                return

    LOGGER.info("Round-robin scan completed: checked %d source(s), published/previewed %d job(s).", checked_count, published_count)
    save_state(state)


if __name__ == "__main__":
    main()
