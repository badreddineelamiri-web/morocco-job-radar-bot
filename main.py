#!/usr/bin/env python3
"""Main entry point for Morocco Job Radar Bot.

The production run fetches official Moroccan job sources, skips already
published jobs, generates a Facebook post plus image, and publishes to the
configured Facebook Page.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any
from collections import defaultdict, deque

sys.path.insert(0, str(Path(__file__).parent / "modules"))

from modules.ai_writer import generate_post
from modules.facebook_publisher import publish_job
from modules.government_sources import fetch_government_jobs
from modules.image_maker import create_job_image
from modules.job_tracker import (
    clean_old_jobs,
    get_published_count,
    is_job_published,
    mark_job_published,
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


def process_job(job: dict[str, Any]) -> str:
    """Generate assets and publish one job.

    Returns a status string: published, skipped, or failed.
    """
    try:
        LOGGER.info("Processing job: %s at %s", job.get("title"), job.get("company"))

        if is_job_published(job):
            LOGGER.info("Job already published, skipping: %s", job.get("title"))
            return "skipped"

        LOGGER.info("Generating AI post...")
        post_data = generate_post(job)

        LOGGER.info("Creating job image...")
        image_path = create_job_image(job, post_data)

        LOGGER.info("Publishing to Facebook...")
        result = publish_job(post_data, image_path)

        if result.get("ok"):
            LOGGER.info("Successfully published job: %s", job.get("title"))
            if result.get("dry_run"):
                LOGGER.info("DRY_RUN result not saved to published jobs tracker.")
            else:
                mark_job_published(job, result)
            return "published"

        LOGGER.error("Failed to publish job: %s", result.get("error", "Unknown error"))
        return "failed"
    except Exception as exc:
        LOGGER.error("Error processing job: %s", exc, exc_info=True)
        return "failed"


def _round_robin_by_source(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Spread publishing across sources so one busy portal does not dominate."""
    groups: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for job in jobs:
        source_key = str(job.get("source") or job.get("source_page") or "unknown")
        groups[source_key].append(job)

    ordered: list[dict[str, Any]] = []
    source_order = deque(groups.keys())
    while source_order:
        source_key = source_order.popleft()
        group = groups[source_key]
        if group:
            ordered.append(group.popleft())
        if group:
            source_order.append(source_key)
    return ordered


def prioritize_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer fresh items and rotate among sources before processing."""
    fresh = [job for job in jobs if not is_job_published(job)]
    already_seen = [job for job in jobs if is_job_published(job)]
    return _round_robin_by_source(fresh) + _round_robin_by_source(already_seen)


def main() -> None:
    """Run one job radar cycle."""
    LOGGER.info("Starting Morocco Job Radar Bot...")

    cleaned = clean_old_jobs(days_to_keep=30)
    if cleaned:
        LOGGER.info("Cleaned %d old jobs from tracker", cleaned)

    max_jobs = _env_int("MAX_JOBS_PER_RUN", default=3)
    LOGGER.info("Fetching official government and agency job sources...")
    jobs = fetch_government_jobs()

    if not jobs:
        LOGGER.warning("No jobs found. Exiting without publishing.")
        return

    jobs = prioritize_jobs(jobs)
    LOGGER.info("Found %d jobs to scan; target is %d new publish(es).", len(jobs), max_jobs)

    published_count = 0
    failed_count = 0
    skipped_count = 0
    processed_count = 0
    for index, job in enumerate(jobs, 1):
        if published_count >= max_jobs:
            LOGGER.info("Publish target reached; stopping scan.")
            break

        LOGGER.info("")
        LOGGER.info("%s", "=" * 50)
        LOGGER.info("Processing candidate job %d/%d", index, len(jobs))
        LOGGER.info("%s", "=" * 50)

        status = process_job(job)
        processed_count += 1
        if status == "published":
            published_count += 1
        elif status == "failed":
            failed_count += 1
        else:
            skipped_count += 1

    LOGGER.info("")
    LOGGER.info("Bot run completed!")
    LOGGER.info("Scanned: %d/%d candidate job(s)", processed_count, len(jobs))
    LOGGER.info("Published: %d/%d target job(s)", published_count, max_jobs)
    LOGGER.info("Skipped: %d job(s)", skipped_count)
    LOGGER.info("Failed: %d job(s)", failed_count)
    LOGGER.info("Total published jobs in tracker: %d", get_published_count())

    if failed_count and os.getenv("DRY_RUN", "").lower() not in {"1", "true", "yes"}:
        raise SystemExit(1)


if __name__ == "__main__":
    if os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}:
        LOGGER.info("DRY RUN mode enabled - no actual publishing")

    main()
