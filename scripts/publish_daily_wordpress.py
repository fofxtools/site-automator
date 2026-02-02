#!/usr/bin/env python3
"""Daily WordPress article publisher with posts_per_day limit enforcement.

Usage:
    python3 scripts/publish_daily_wordpress.py --site-id <site_id>
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from site_automator.publisher import publish_posts_wordpress
from site_automator.sites import load_site_config
from site_automator.wordpress import WordPressDeployer
from site_automator.wordops import WordOpsProvisioner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# File logging (if configured)
log_file = os.getenv("LOG_FILE")
if log_file:
    log_file_level = os.getenv("LOG_FILE_LEVEL", "ERROR").upper()
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_file_level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    )
    logging.getLogger().addHandler(file_handler)

# Silence paramiko's noisy INFO logs
logging.getLogger("paramiko").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def count_posts_activated_today(site_id: str) -> int:
    """Count posts activated today for a site.

    Args:
        site_id: Site identifier

    Returns:
        Number of posts activated today
    """
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    published_dir = content_root / site_id / "articles" / "published"

    if not published_dir.exists():
        return 0

    today = datetime.now(timezone.utc).date()
    count = 0

    for pub_file in published_dir.glob("*.json"):
        try:
            with pub_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if published_at exists and is from today
            published_at = data.get("published_at")
            if published_at:
                published_dt = datetime.fromisoformat(published_at)
                # Ensure timezone-aware comparison
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
                if published_dt.astimezone(timezone.utc).date() == today:
                    count += 1
        except (json.JSONDecodeError, ValueError, KeyError):
            # Skip malformed files
            continue

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Publish WordPress articles respecting daily limits"
    )
    parser.add_argument(
        "--site-id",
        required=True,
        help="Site ID from sites.csv",
    )
    args = parser.parse_args()

    site_id = args.site_id

    try:
        # Load site config
        site = load_site_config(site_id)
        posts_per_day = int(site["posts_per_day"])

        logger.info(
            f"Starting daily publishing for {site_id} "
            f"(limit: {posts_per_day} posts/day)"
        )

        # Count posts already activated today
        activated_today = count_posts_activated_today(site_id)
        logger.info(f"Posts already activated today: {activated_today}")

        # Calculate remaining quota
        remaining = max(0, posts_per_day - activated_today)
        logger.info(f"Remaining quota for today: {remaining}")

        if remaining == 0:
            logger.info("Daily limit already reached, nothing to do")
            return 0

        # Connect to WordPress
        wordops = WordOpsProvisioner.from_env()
        try:
            wordpress = WordPressDeployer(wordops)

            # Activate articles up to remaining quota
            publish_posts_wordpress(site_id, wordpress, limit=remaining)

            logger.info(f"Daily publishing complete for {site_id}")
            return 0
        finally:
            wordops.close()

    except Exception as e:
        logger.error(f"Error publishing for {site_id}: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
