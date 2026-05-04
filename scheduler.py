#!/usr/bin/env python3
"""Scheduler for Morocco Job Radar Bot.

This script can be run periodically (e.g., every hour) to check for new jobs.
It's designed to be run by Windows Task Scheduler or a similar tool.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent / "modules"))

from modules.job_tracker import clean_old_jobs


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger("Scheduler")


def run_bot() -> bool:
    """Run the main bot script."""
    try:
        LOGGER.info("🚀 Starting bot from scheduler...")
        
        # Import here to avoid circular imports
        from main import main
        
        # Clean old jobs periodically (every 24 hours)
        if time.time() % (24 * 3600) < 60:  # Roughly once per day
            cleaned = clean_old_jobs(days_to_keep=30)
            if cleaned:
                LOGGER.info(f"Cleaned {cleaned} old jobs from tracker")
        
        # Run the main bot
        main()
        return True
        
    except Exception as exc:
        LOGGER.error(f"Bot run failed: {exc}", exc_info=True)
        return False


def main() -> None:
    """Main scheduler function."""
    LOGGER.info("📅 Morocco Job Radar Bot Scheduler")
    LOGGER.info("=" * 50)
    
    # Check if DRY_RUN is set
    dry_run = os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}
    if dry_run:
        LOGGER.info("🔍 DRY_RUN mode enabled")
    
    # Run the bot
    success = run_bot()
    
    if success:
        LOGGER.info("✅ Scheduler run completed successfully")
    else:
        LOGGER.error("❌ Scheduler run failed")
    
    LOGGER.info("=" * 50)


if __name__ == "__main__":
    main()
