#!/usr/bin/env python3
"""Daily WordPress article creator with posts_per_day limit enforcement.

Usage:
    python3 scripts/create_daily_wordpress.py --site-id <site_id>
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from site_automator.utils import configure_logging
from site_automator.publisher import create_posts_wordpress
from site_automator.sites import load_site_config
from site_automator.wordops import WordOpsProvisioner
from site_automator.wordpress import WordPressDeployer

configure_logging(console_level="INFO")

logger = logging.getLogger(__name__)


def count_posts_created_today(site_id: str) -> int:
    """Count posts created today for a site.

    Args:
        site_id: Site identifier

    Returns:
        Number of posts created today
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

            # Check if created_at exists and is from today
            created_at = data.get("created_at")
            if created_at:
                created_dt = datetime.fromisoformat(created_at)
                # Ensure timezone-aware comparison
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                if created_dt.astimezone(timezone.utc).date() == today:
                    count += 1
        except (json.JSONDecodeError, ValueError, KeyError):
            # Skip malformed files
            continue

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Create WordPress articles respecting daily limits"
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
        server = site["server"]

        logger.info(
            f"Starting daily creation for {site_id} "
            f"(limit: {posts_per_day} posts/day, server: {server})"
        )

        # Count posts already created today
        created_today = count_posts_created_today(site_id)
        logger.info(f"Posts already created today: {created_today}")

        # Calculate remaining quota
        remaining = max(0, posts_per_day - created_today)
        logger.info(f"Remaining quota for today: {remaining}")

        if remaining == 0:
            logger.info("Daily limit already reached, nothing to do")
            return 0

        # Connect to WordPress
        wordops = WordOpsProvisioner(host=server)
        try:
            wordpress = WordPressDeployer(wordops)

            # Create articles up to remaining quota
            create_posts_wordpress(site_id, wordpress, limit=remaining)

            logger.info(f"Daily creation complete for {site_id}")
            return 0
        finally:
            wordops.close()

    except Exception as e:
        logger.error(f"Error creating for {site_id}: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
